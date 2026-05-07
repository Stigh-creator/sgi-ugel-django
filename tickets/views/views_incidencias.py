from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.http import require_POST

from auditoria.utils import registrar_auditoria
from .views_utils import (
    is_admin, is_fetch_request, add_form_errors_to_messages, HttpResponseClientRefresh, page_querystring
)
from ..models import Area, Comentario, CustomUser, Incidencia, IncidenciaImagen, Estado
from ..forms.forms_incidencias import (
    IncidenciaAdminForm,
    IncidenciaForm,
    ComentarioForm,
    ReabrirIncidenciaForm,
    IncidenciaCierreForm,
)
from ..services import (
    apply_estado_filter,
    apply_incidencias_search,
    aceptar_incidencia_service,
    available_estado_filters,
    assign_incidencia_service,
    cerrar_incidencia_service,
    create_incidencia_service,
    get_active_ticket_load_for_user,
    get_visible_incidencias_queryset,
    optimized_incidencias_queryset,
    rechazar_incidencia_service,
    resolve_active_tab_for_user,
    reabrir_incidencia_service,
    resolver_incidencia_service,
    compatible_replacement_type_ids,
    equipos_ocupados_por_incidencias,
    emitir_evento_incidencia,
    IncidenciaService,
)
from inventario.models import Marca, TipoEquipo, Equipo, EstadoEquipo

def crear_comentario_estado(*, incidencia, usuario, texto, tipo="confirmacion", evidencia=None):
    comentario = Comentario.objects.create(
        incidencia=incidencia,
        usuario=usuario,
        tipo_comentario=tipo,
        texto=texto,
        evidencia_adjunta=evidencia,
    )
    return comentario


def ticket_label(incidencia):
    return f"[{incidencia.codigo or f'INC-{incidencia.pk:04d}'}]"


def nombre_usuario(usuario):
    if not usuario:
        return "Sin usuario registrado"
    return usuario.get_full_name() or usuario.username


def prioridad_label(value):
    return dict(Incidencia.PRIORIDAD_CHOICES).get(value, value or "Sin prioridad")


def equipo_label(equipo):
    if not equipo:
        return "equipo no institucional"
    return f"{equipo.codigo_equipo} - {equipo.nombre_equipo}"


def format_timedelta_humano(delta):
    seconds = int(abs(delta.total_seconds()))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = max(1, remainder // 60) if days == 0 and hours == 0 else remainder // 60
    parts = []
    if days:
        parts.append(f"{days} día{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
    if not days and minutes:
        parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
    return " y ".join(parts[:2]) or "menos de 1 minuto"


def build_sla_notice(incidencia, user):
    if incidencia.tecnico_asignado_id != user.id:
        return None
    if incidencia.estado_actual in {Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO}:
        return None
    if incidencia.estado_sla in {"cumplido", "no_aplica"}:
        return None

    tipo = "resolución"
    deadline = incidencia.fecha_limite_resolucion
    if incidencia.estado_actual == Incidencia.ESTADO_ASIGNADO and incidencia.fecha_limite_respuesta:
        tipo = "respuesta"
        deadline = incidencia.fecha_limite_respuesta
    if not deadline:
        return None

    now = timezone.now()
    delta = deadline - now
    vencido = delta.total_seconds() <= 0
    return {
        "tipo": tipo,
        "fecha": timezone.localtime(deadline),
        "vencido": vencido,
        "tiempo": format_timedelta_humano(delta),
        "estado": incidencia.get_estado_sla_display(),
    }


@login_required
def index(request):
    if is_admin(request.user):
        return redirect("dashboard_admin")
    if request.user.es_tecnico:
        return redirect("dashboard_tecnico")
    return redirect("mis_incidencias")

@login_required
@user_passes_test(is_admin)
def dashboard_admin(request):
    hoy = timezone.localdate()
    count_criticas = Incidencia.objects.filter(
        Q(prioridad__icontains='alt') | Q(prioridad__icontains='crit')
    ).exclude(estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]).count()

    count_pendientes = Incidencia.objects.filter(
        estado__name__in=[
            Incidencia.ESTADO_PENDIENTE,
            Incidencia.ESTADO_ASIGNADO,
            Incidencia.ESTADO_EN_PROCESO,
            Incidencia.ESTADO_RECHAZADO,
            Incidencia.ESTADO_REABIERTO,
        ]
    ).count()

    count_resueltas = Incidencia.objects.filter(estado__name__iexact=Incidencia.ESTADO_RESUELTO).count()
    count_cerrados = Incidencia.objects.filter(estado__name__iexact=Incidencia.ESTADO_CERRADO).count()

    lista_hoy = Incidencia.objects.filter(fecha_creacion__date=hoy).select_related('area', 'estado', 'creador').order_by('-fecha_creacion')
    count_hoy = lista_hoy.count()

    return render(request, 'tickets/dashboard_admin.html', {
        'stats': {
            'total_criticas': count_criticas,
            'total_pendientes': count_pendientes,
            'total_resueltos': count_resueltas,
            'total_cerrados': count_cerrados,
            'total_hoy': count_hoy,
        },
        'incidencias_hoy_lista': lista_hoy,
        'estados_lista': Estado.objects.all(),
        'tecnicos_lista': CustomUser.objects.filter(role=CustomUser.ROL_TECNICO, is_active=True),
    })

@login_required
def dashboard_tecnico(request):
    if not request.user.es_tecnico:
        return redirect("index")
        
    tickets_base = Incidencia.objects.filter(tecnico_asignado=request.user)
    hoy = timezone.localdate()
    
    count_criticas = tickets_base.filter(
        Q(prioridad__icontains='alt') | Q(prioridad__icontains='crit')
    ).exclude(estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]).count()

    count_finalizados = tickets_base.filter(estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]).count()
    
    ultimas_incidencias = tickets_base.filter(fecha_creacion__date=hoy).select_related('area', 'estado', 'creador').order_by('-fecha_creacion')

    return render(request, 'tickets/dashboard_tecnico.html', {
        'assigned_tickets': tickets_base.count(),
        'assigned_criticas': count_criticas,
        'resolved_assigned_tickets': count_finalizados,
        'ultimas_incidencias': ultimas_incidencias,
        'incidencias_hoy': ultimas_incidencias.count(),
        'estados_lista': Estado.objects.all(),
    })

@login_required
def mis_incidencias(request):
    return incidencias_list(request)

@login_required
def incidencias_list(request):
    user = request.user
    q = request.GET.get("q", "")
    estado_f = request.GET.get("estado", "")
    area_f = request.GET.get("area", "")
    prioridad_f = request.GET.get("prioridad", "")
    order_f = request.GET.get("order", "-fecha_creacion")
    
    active_tab = resolve_active_tab_for_user(user, request.GET.get("tab"))
    queryset, active_tab = get_visible_incidencias_queryset(user, active_tab)

    queryset = apply_incidencias_search(queryset, q)
    queryset = apply_estado_filter(queryset, estado_f)
    if area_f:
        queryset = queryset.filter(area_id=area_f)
    if prioridad_f:
        queryset = queryset.filter(prioridad=prioridad_f)

    allowed_ordering = {
        "-fecha_creacion": "-fecha_creacion",
        "fecha_creacion": "fecha_creacion",
        "prioridad": "prioridad",
        "-prioridad": "-prioridad",
        "area": "area__name",
        "-area": "-area__name",
        "codigo": "codigo",
        "-codigo": "-codigo",
    }
    queryset = optimized_incidencias_queryset(queryset).order_by(allowed_ordering.get(order_f, "-fecha_creacion"))
    
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "incidencias": page_obj,
        "estados": available_estado_filters(),
        "query": q,
        "estado_selected": estado_f,
        "area_selected": area_f,
        "prioridad_selected": prioridad_f,
        "order_selected": order_f,
        "active_tab": active_tab,
        "now": timezone.localtime(timezone.now()),
        "areas": Area.objects.all().order_by("name"),
        "prioridades": Incidencia.PRIORIDAD_CHOICES,
        "page_querystring": page_querystring(request),
    }

    if request.headers.get("HX-Request"):
        return render(request, "tickets/partials/incidencias_table.html", context)

    return render(request, "tickets/incidencias_list.html", context)

@login_required
def crear_incidencia(request):
    es_adm = is_admin(request.user)
    
    if request.method == 'POST':
        if es_adm:
            form = IncidenciaAdminForm(request.POST, request.FILES)
        else:
            form = IncidenciaForm(request.POST, request.FILES, user=request.user)
            
        if form.is_valid():
            incidencia = form.save(commit=False)
            incidencia.creador = request.user
            
            if not es_adm:
                incidencia.area = request.user.area
                if request.user.es_usuario:
                    incidencia.prioridad = Incidencia.PRIORIDAD_MEDIA
            try:
                create_incidencia_service(
                    incidencia=incidencia,
                    extra_images=[form.cleaned_data.get("imagen_2"), form.cleaned_data.get("imagen_3")],
                )
            except ValidationError as exc:
                form.add_error("equipo", exc.message)
                add_form_errors_to_messages(request, form)
                context = {
                    'form': form,
                    'es_admin': es_adm,
                    'areas': Area.objects.all(),
                    'categorias': Incidencia.CATEGORIA_CHOICES,
                    'prioridades': Incidencia.PRIORIDAD_CHOICES,
                }
                return render(request, "tickets/crear_incidencia.html", context)
            
            messages.success(request, f"Incidencia {incidencia.codigo} registrada correctamente.")
            return redirect('incidencias_list')
        else:
            add_form_errors_to_messages(request, form)
    else:
        if es_adm:
            form = IncidenciaAdminForm()
        else:
            form = IncidenciaForm(user=request.user)
    
    context = {
        'form': form,
        'es_admin': es_adm,
        'areas': Area.objects.all(),
        'categorias': Incidencia.CATEGORIA_CHOICES,
        'prioridades': Incidencia.PRIORIDAD_CHOICES,
    }
    return render(request, "tickets/crear_incidencia.html", context)

@login_required
def detalle_incidencia(request, pk):
    incidencia = get_object_or_404(optimized_incidencias_queryset(), pk=pk)
    
    if not is_admin(request.user):
        if request.user.es_tecnico and incidencia.tecnico_asignado != request.user:
            messages.error(request, "No estás asignado a esta incidencia.")
            return redirect('incidencias_list')
        if request.user.es_usuario and incidencia.creador != request.user:
            messages.error(request, "No tienes permiso para ver esta incidencia.")
            return redirect('incidencias_list')
    
    from auditoria.models import Auditoria
    from inventario.models import Equipo, EstadoEquipo
    logs = Auditoria.objects.filter(modulo="Incidencias", referencia_id=pk).order_by("-fecha_hora")
    comentarios = incidencia.comentarios.all().order_by("fecha_creacion")
    if incidencia.tecnico_asignado_id != request.user.id:
        comentarios = comentarios.exclude(
            tipo_comentario="observacion",
            texto__icontains="SLA",
        )
    
    timeline = []
    for log in logs:
        timeline.append({'tipo': 'log', 'fecha': log.fecha_hora, 'data': log})
    for com in comentarios:
        timeline.append({'tipo': 'comentario', 'fecha': com.fecha_creacion, 'data': com})
    
    timeline.sort(key=lambda x: x['fecha'], reverse=True)
        
    typing_data = cache.get(f"typing_list_{incidencia.id}", {})
    typing_users = []
    ahora = timezone.now().timestamp()
    
    for uid, info in list(typing_data.items()):
        if info['expires'] < ahora:
            typing_data.pop(uid)
        elif int(uid) != request.user.id:
            typing_users.append(info['name'])
            
    estado_operativo = EstadoEquipo.objects.filter(nombre="Operativo").first()
    equipos_reemplazo = Equipo.objects.filter(
        activo=True,
        estado_tecnico=estado_operativo,
        disponibilidad=Equipo.DISPONIBILIDAD_LIBRE,
    )
    if incidencia.equipo_id:
        equipos_reemplazo = equipos_reemplazo.filter(
            tipo_equipo_id__in=compatible_replacement_type_ids(incidencia.equipo.tipo_equipo)
        ).exclude(pk=incidencia.equipo_id)
    equipos_reemplazo = equipos_reemplazo.exclude(
        pk__in=equipos_ocupados_por_incidencias(exclude_incidencia_id=incidencia.pk)
    )

    context = {
        'incidencia': incidencia,
        'timeline': timeline,
        'comentarios': comentarios,
        'typing_users': typing_users,
        'puede_aceptar_rechazar': (
            incidencia.tecnico_asignado_id == request.user.id
            and incidencia.estado_actual == Incidencia.ESTADO_ASIGNADO
        ),
        'tecnicos': CustomUser.objects.filter(
            role__in=[CustomUser.ROL_ADMIN, CustomUser.ROL_TECNICO],
            is_active=True,
        ),
        'comentario_form': ComentarioForm(),
        'reabrir_form': ReabrirIncidenciaForm(),
        'equipos_reemplazo': equipos_reemplazo.select_related("area", "marca", "tipo_equipo"),
        'now': timezone.localtime(timezone.now()),
        'sla_notice': build_sla_notice(incidencia, request.user),
    }

    if request.headers.get('HX-Request') and not request.method == 'POST':
        return render(request, 'tickets/partials/_comentarios_list.html', {
            'comentarios': comentarios,
            'typing_users': typing_users
        })

    return render(request, "tickets/detalle_incidencia.html", context)

@login_required
@require_POST
def marcar_escribiendo(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    
    puedo_ver = is_admin(request.user) or \
                (request.user.es_tecnico and incidencia.tecnico_asignado == request.user) or \
                (request.user.es_usuario and incidencia.creador == request.user)
                
    if not puedo_ver:
        return HttpResponse(status=403)

    cache_key = f"typing_list_{pk}"
    typing_data = cache.get(cache_key, {})
    
    typing_data[str(request.user.id)] = {
        'name': request.user.get_full_name() or request.user.username,
        'expires': timezone.now().timestamp() + 7
    }
    
    cache.set(cache_key, typing_data, 10) 
    return HttpResponse(status=204)

@login_required
@require_POST
def asignar_tecnico(request, pk):
    if not is_admin(request.user):
        return JsonResponse({"success": False, "message": "No tienes permisos."}, status=403)
    
    incidencia = get_object_or_404(Incidencia, pk=pk)
    tecnico_id = request.POST.get("tecnico_id")
    tecnico = get_object_or_404(CustomUser, pk=tecnico_id)
    try:
        current_load = get_active_ticket_load_for_user(tecnico, exclude_incidencia_id=incidencia.pk)
        IncidenciaService.asignar(
            incidencia.pk,
            tecnico=tecnico,
            actor=request.user,
            fecha_programada=request.POST.get("fecha_programada"),
            hora_programada=request.POST.get("hora_programada"),
            observaciones=request.POST.get("observaciones"),
        )
    except ValidationError as exc:
        messages.error(request, exc.message)
        return HttpResponseClientRefresh()
    
    messages.success(request, f"Técnico {tecnico.first_name} asignado a la incidencia {incidencia.codigo}")
    return HttpResponseClientRefresh()


@login_required
@require_POST
def aceptar_incidencia(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    try:
        aceptar_incidencia_service(incidencia, request.user)
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect("detalle_incidencia", pk=pk)

    messages.success(request, f"Incidencia {incidencia.codigo} aceptada. Ya puedes registrar la solución cuando corresponda.")
    return redirect("detalle_incidencia", pk=pk)


@login_required
@require_POST
def rechazar_incidencia(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    especialista_nombre = request.user.get_full_name() or request.user.username
    try:
        motivo = rechazar_incidencia_service(incidencia, request.user, request.POST.get("motivo"))
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect("detalle_incidencia", pk=pk)

    messages.warning(request, f"Incidencia {incidencia.codigo} rechazada. El motivo quedó registrado en el seguimiento.")
    return redirect("incidencias_list")


@login_required
def get_equipos_for_area(request):
    area_id = request.GET.get("area") or request.GET.get("id_area")
    user = request.user
    estado_operativo = EstadoEquipo.objects.filter(nombre="Operativo").first()
    
    if user.es_usuario:
        if user.area and user.area.sede_principal:
            equipos = Equipo.objects.filter(
                area__sede_principal=user.area.sede_principal,
                activo=True,
                estado_tecnico=estado_operativo,
            ).distinct()
        else:
            equipos = Equipo.objects.none()
    else:
        if area_id:
            selected_area = Area.objects.filter(pk=area_id).first()
            if selected_area and selected_area.sede_principal:
                equipos = Equipo.objects.filter(
                    area__sede_principal=selected_area.sede_principal,
                    activo=True,
                    estado_tecnico=estado_operativo,
                )
            else:
                equipos = Equipo.objects.none()
        else:
            equipos = Equipo.objects.none()
            
    return render(request, "tickets/partials/equipo_options.html", {"equipos": equipos.distinct().order_by("codigo_equipo")})

@login_required
def crear_incidencia_modal(request):
    is_adm = is_admin(request.user)
    FormClass = IncidenciaAdminForm if is_adm else IncidenciaForm
    is_htmx = bool(request.headers.get("HX-Request"))

    def render_fullscreen_create(form):
        return render(
            request,
            "tickets/crear_incidencia.html",
            {
                "form": form,
                "es_admin": is_adm,
                "areas": Area.objects.all(),
                "categorias": Incidencia.CATEGORIA_CHOICES,
                "prioridades": Incidencia.PRIORIDAD_CHOICES,
            },
        )
    
    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, user=request.user) if not is_adm else FormClass(request.POST, request.FILES)
        if form.is_valid():
            incidencia = form.save(commit=False)
            incidencia.creador = request.user
            if not is_adm:
                incidencia.area = request.user.area
                if request.user.es_usuario:
                    incidencia.prioridad = Incidencia.PRIORIDAD_MEDIA
            
            equipo_id = request.POST.get("equipo")
            if equipo_id == "otro":
                tipo_n = form.cleaned_data.get("otro_tipo")
                marca_n = form.cleaned_data.get("otro_marca")
                modelo = form.cleaned_data.get("otro_modelo")
                serie = form.cleaned_data.get("otro_serie")
                
                if is_adm:
                    tipo_obj, _ = TipoEquipo.objects.get_or_create(nombre=tipo_n)
                    marca_obj, _ = Marca.objects.get_or_create(nombre=marca_n)
                    estado_operativo = EstadoEquipo.objects.filter(nombre="Operativo").first()
                    nuevo_equipo = Equipo.objects.create(
                        codigo_equipo=f"AUTO-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        nombre_equipo=f"{tipo_n} {marca_n} {modelo}",
                        tipo_equipo=tipo_obj,
                        marca=marca_obj,
                        modelo=modelo,
                        numero_serie=serie,
                        area=incidencia.area,
                        estado=estado_operativo,
                        estado_tecnico=estado_operativo,
                        observaciones=f"Activo creado automáticamente desde reporte de incidencia."
                    )
                    incidencia.equipo = nuevo_equipo
            elif equipo_id and equipo_id != "otro":
                incidencia.equipo_id = equipo_id

            try:
                create_incidencia_service(
                    incidencia=incidencia,
                    extra_images=[form.cleaned_data.get("imagen_2"), form.cleaned_data.get("imagen_3")],
                )
            except ValidationError as exc:
                form.add_error("equipo", exc.message)
                if is_htmx:
                    return render(
                        request,
                        "tickets/partials/modal_incidencia_form.html",
                        {"form": form, "es_admin": is_adm, "action_url": request.path},
                        status=400,
                    )
                add_form_errors_to_messages(request, form)
                return render_fullscreen_create(form)

            if is_htmx:
                return HttpResponseClientRefresh()
            messages.success(request, f"Incidencia {incidencia.codigo} registrada correctamente.")
            return redirect("incidencias_list")

        if is_htmx:
            return render(
                request,
                "tickets/partials/modal_incidencia_form.html",
                {"form": form, "es_admin": is_adm, "action_url": request.path},
            )
        add_form_errors_to_messages(request, form)
        return render_fullscreen_create(form)

    form = FormClass(user=request.user) if not is_adm else FormClass()
    if is_htmx:
        return render(
            request,
            "tickets/partials/modal_incidencia_form.html",
            {"form": form, "es_admin": is_adm, "action_url": request.path},
        )
    return redirect("crear_incidencia")

@login_required
@require_POST
def agregar_comentario(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    if incidencia.estado_actual in {Incidencia.ESTADO_RECHAZADO, Incidencia.ESTADO_CERRADO}:
        return JsonResponse({"success": False, "message": "El seguimiento está bloqueado para esta incidencia."}, status=403)

    form = ComentarioForm(request.POST, request.FILES)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.incidencia = incidencia
        comentario.usuario = request.user
        comentario.save()
        
        emitir_evento_incidencia("incidencia.comentada", incidencia, actor=request.user, metadata={"comentario_id": comentario.id})
        
        comentarios = incidencia.comentarios.all().order_by("fecha_creacion")
        return render(request, 'tickets/partials/_comentarios_list.html', {'comentarios': comentarios, 'typing_users': []})
    
    return JsonResponse({"success": False, "message": "Error al guardar comentario."}, status=400)

@login_required
@require_POST
def resolver_incidencia(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    
    if request.user != incidencia.tecnico_asignado and not is_admin(request.user):
        messages.error(request, "No tienes permiso para resolver esta incidencia.")
        return redirect('detalle_incidencia', pk=pk)

    if not incidencia.puede_registrar_solucion:
        messages.error(request, "La incidencia debe estar en proceso o reabierta para registrar la solución.")
        return redirect('detalle_incidencia', pk=pk)
        
    form = IncidenciaCierreForm(request.POST, request.FILES, incidencia=incidencia)
    if form.is_valid():
        solucion = form.cleaned_data["solucion_aplicada"]
        tipo_resolucion = form.cleaned_data["tipo_resolucion"]
        equipo_reemplazo = form.cleaned_data.get("equipo_reemplazo")
        resolver_incidencia_service(
            incidencia=incidencia,
            tecnico=request.user,
            solucion_aplicada=solucion,
            tipo_resolucion=tipo_resolucion,
            equipo_reemplazo=equipo_reemplazo,
            evidencia=form.cleaned_data.get("evidencia_solucion"),
            evidencia_2=form.cleaned_data.get("evidencia_solucion_2"),
            evidencia_3=form.cleaned_data.get("evidencia_solucion_3")
        )
        messages.success(request, f"Incidencia #{pk} marcada como resuelta.")
        return redirect('detalle_incidencia', pk=pk)
    
    add_form_errors_to_messages(request, form)
    return redirect('detalle_incidencia', pk=pk)

@login_required
@require_POST
def reabrir_incidencia(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    
    if request.user != incidencia.creador and not is_admin(request.user):
        messages.error(request, "Solo el solicitante puede reabrir la incidencia.")
        return redirect('detalle_incidencia', pk=pk)

    form = ReabrirIncidenciaForm(request.POST, request.FILES)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect('detalle_incidencia', pk=pk)

    IncidenciaService.reabrir(incidencia.pk, request.user, motivo=form.cleaned_data["motivo"].strip())

    motivo = form.cleaned_data["motivo"].strip()
    imagenes = [
        form.cleaned_data.get("imagen_1"),
        form.cleaned_data.get("imagen_2"),
        form.cleaned_data.get("imagen_3"),
    ]
    imagen_principal = next((img for img in imagenes if img), None)
    imagenes_extra = []
    principal_usada = False
    for imagen in imagenes:
        if not imagen:
            continue
        if not principal_usada and imagen is imagen_principal:
            principal_usada = True
            continue
        imagenes_extra.append(imagen)
    crear_comentario_estado(
        incidencia=incidencia,
        usuario=request.user,
        tipo="persiste",
        evidencia=imagen_principal,
        texto=(
            f"{request.user.get_full_name() or request.user.username} reabrió la incidencia.\n"
            f"Motivo: {motivo}"
        ),
    )
    for imagen_extra in imagenes_extra:
        if imagen_extra:
            IncidenciaImagen.objects.create(incidencia=incidencia, imagen=imagen_extra)
    
    messages.warning(request, f"Incidencia #{pk} ha sido reabierta.")
    return redirect('detalle_incidencia', pk=pk)

@login_required
@require_POST
def cerrar_incidencia(request, pk):
    incidencia = get_object_or_404(Incidencia, pk=pk)
    
    if request.user != incidencia.creador and not is_admin(request.user):
        return JsonResponse({"success": False, "message": "No tienes permiso."}, status=403)
        
    cerrar_incidencia_service(incidencia, request.user)
    return JsonResponse({"success": True})

@login_required
def gestionar_incidencia(request, pk):
    if not is_admin(request.user):
        messages.error(request, "Acceso denegado.")
        return redirect('incidencias_list')
        
    incidencia = get_object_or_404(Incidencia, pk=pk)
    if incidencia.estado_actual in {Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO}:
        lock_message = (
            "Esta incidencia ya fue resuelta y está esperando la confirmación del creador o una reapertura."
            if incidencia.estado_actual == Incidencia.ESTADO_RESUELTO
            else "Esta incidencia ya está cerrada y no admite cambios de asignación o programación."
        )
        if request.headers.get("HX-Request"):
            return HttpResponse(
                f"""
                <div class="modal-header border-0 pb-0">
                    <h5 class="modal-title fw-bold">Gestión bloqueada</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                </div>
                <div class="modal-body pt-2 pb-4">
                    <div class="alert alert-warning rounded-4 mb-0">
                        <i class="bi bi-lock-fill me-2"></i>{lock_message}
                    </div>
                </div>
                """
            )
        messages.warning(request, lock_message)
        return redirect('detalle_incidencia', pk=pk)
    
    if request.method == 'POST':
        form = IncidenciaAdminForm(request.POST, request.FILES, instance=incidencia)
        if form.is_valid():
            old_snapshot = Incidencia.objects.select_related("tecnico_asignado", "estado").get(pk=pk)
            old_tecnico = old_snapshot.tecnico_asignado
            old_priority = old_snapshot.prioridad
            incidencia = form.save(commit=False)
            new_tecnico = form.cleaned_data.get("tecnico_asignado")
            
            reassigned = False
            if new_tecnico != old_tecnico:
                incidencia.fecha_asignacion = timezone.now()
                incidencia.estado = Estado.objects.get_or_create(name=Incidencia.ESTADO_ASIGNADO)[0]
                reassigned = True
            
            incidencia.save()
            if reassigned:
                from inventario.services import marcar_equipo_en_reparacion_por_asignacion

                marcar_equipo_en_reparacion_por_asignacion(
                    equipo=incidencia.equipo,
                    usuario=new_tecnico,
                    incidencia_codigo=incidencia.codigo,
                )
            final_priority = incidencia.prioridad
            for img_field in ["imagen_2", "imagen_3"]:
                img = form.cleaned_data.get(img_field)
                if img:
                    IncidenciaImagen.objects.create(incidencia=incidencia, imagen=img)

            if reassigned:
                action = "reasignó técnico" if old_tecnico else "asignó técnico"
                new_name = nombre_usuario(new_tecnico)
                if old_tecnico:
                    old_name = nombre_usuario(old_tecnico)
                    detail = f"{ticket_label(incidencia)} Reasignado de {old_name} a {new_name} por {nombre_usuario(request.user)}."
                else:
                    detail = f"{ticket_label(incidencia)} Asignación inicial de técnico: {new_name}. Acción realizada por {nombre_usuario(request.user)}."
            else:
                action = "gestionó ticket"
                detail = f"{ticket_label(incidencia)} Configuración administrativa actualizada por {nombre_usuario(request.user)}."
            
            registrar_auditoria(request, "Incidencias", action, detail, pk)

            if old_priority != final_priority:
                registrar_auditoria(
                    request,
                    "Incidencias",
                    "actualizó prioridad",
                    f"{ticket_label(incidencia)} Prioridad actualizada de {prioridad_label(old_priority)} a {prioridad_label(final_priority)}.",
                    pk,
                )
            
            if request.headers.get("HX-Request"):
                return HttpResponseClientRefresh()
            messages.success(request, f"Ticket #{pk} actualizado correctamente.")
            return redirect('detalle_incidencia', pk=pk)
        else:
            add_form_errors_to_messages(request, form)
    else:
        form = IncidenciaAdminForm(instance=incidencia)

    template_name = (
        "tickets/partials/modal_incidencia_gestion.html"
        if request.headers.get("HX-Request")
        else "tickets/incidencia_gestion.html"
    )
    return render(request, template_name, {"form": form, "incidencia": incidencia})
