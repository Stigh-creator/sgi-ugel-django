from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import F, Q, Count
from django.core.paginator import Paginator
from django.urls import reverse
from django.http import FileResponse, Http404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Equipo, Marca, TipoEquipo, EstadoEquipo, MantenimientoPreventivo, Repuesto
from .forms import (
    EquipoEstadoUpdateForm,
    EquipoForm,
    MantenimientoCompletarForm,
    MantenimientoPreventivoForm,
    RepuestoForm,
    RepuestoStockForm,
)
from .services import registrar_cambio_manual_estado_equipo
from tickets.models import Area, CustomUser
from tickets.views.views_utils import add_form_errors_to_messages, page_querystring
from tickets.services import normalize_expression, normalize_text
from tickets.utils.exports import generate_excel_inventario, generate_pdf
from auditoria.utils import registrar_auditoria

def can_view_inventory(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role in {CustomUser.ROL_ADMIN, CustomUser.ROL_ALMACEN, CustomUser.ROL_TECNICO}
    )


def can_view_inventory_control(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role in {CustomUser.ROL_ADMIN, CustomUser.ROL_ALMACEN}
    )


def can_manage_inventory(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role == CustomUser.ROL_ALMACEN
    )


def inventory_export_querystring(request):
    querydict = request.GET.copy()
    querydict.pop("page", None)
    encoded = querydict.urlencode()
    return f"?{encoded}" if encoded else ""


def control_operativo_querystring(request, *exclude_keys):
    querydict = request.GET.copy()
    for key in exclude_keys:
        querydict.pop(key, None)
    encoded = querydict.urlencode()
    return f"&{encoded}" if encoded else ""


def usuarios_mantenimiento_queryset():
    return CustomUser.objects.filter(
        is_active=True,
        role__in=[CustomUser.ROL_TECNICO, CustomUser.ROL_ADMIN, CustomUser.ROL_ALMACEN],
    ).order_by("first_name", "last_name")


def get_filtered_equipos_queryset(request):
    vista = request.GET.get('vista', 'activos')
    equipos_list = Equipo.objects.select_related('area', 'marca', 'tipo_equipo', 'estado_tecnico').order_by('-fecha_register')
    if vista == 'bajas':
        equipos_list = equipos_list.filter(activo=False)
    else:
        equipos_list = equipos_list.filter(activo=True)

    q = request.GET.get('q')
    area_id = request.GET.get('area')
    estado = request.GET.get('estado')
    disponibilidad = request.GET.get('disponibilidad')
    marca_id = request.GET.get('marca')
    tipo_id = request.GET.get('tipo')
    
    if q:
        normalized_q = normalize_text(q)
        equipos_list = equipos_list.annotate(
            nombre_normalizado=normalize_expression('nombre_equipo'),
            marca_normalizada=normalize_expression('marca__nombre'),
            modelo_normalizado=normalize_expression('modelo'),
            serie_normalizada=normalize_expression('numero_serie'),
            area_normalizada=normalize_expression('area__name'),
        ).filter(
            Q(codigo_equipo__icontains=q)
            | Q(nombre_normalizado__contains=normalized_q)
            | Q(marca_normalizada__contains=normalized_q)
            | Q(modelo_normalizado__contains=normalized_q)
            | Q(serie_normalizada__contains=normalized_q)
            | Q(area_normalizada__contains=normalized_q)
        )
    if area_id:
        equipos_list = equipos_list.filter(area_id=area_id)
    if estado:
        equipos_list = equipos_list.filter(estado_tecnico__nombre=estado)
    if disponibilidad:
        equipos_list = equipos_list.filter(disponibilidad=disponibilidad)
    if marca_id:
        equipos_list = equipos_list.filter(marca_id=marca_id)
    if tipo_id:
        equipos_list = equipos_list.filter(tipo_equipo_id=tipo_id)

    return equipos_list


def get_inventario_context(request, form=None):
    vista = request.GET.get('vista', 'activos')
    equipos_list = get_filtered_equipos_queryset(request)
    areas = Area.objects.all()
    q = request.GET.get('q')
    area_id = request.GET.get('area')
    estado = request.GET.get('estado')
    disponibilidad = request.GET.get('disponibilidad')
    marca_id = request.GET.get('marca')
    tipo_id = request.GET.get('tipo')

    stats = Equipo.objects.filter(activo=True).aggregate(
        total=Count('id'),
        operativos=Count('id', filter=Q(estado_tecnico__nombre='Operativo')),
        en_revision=Count('id', filter=Q(estado_tecnico__nombre='En revisión')),
        reparacion=Count('id', filter=Q(estado_tecnico__nombre='En reparación')),
        inoperativos=Count('id', filter=Q(estado_tecnico__nombre='Inoperativo')),
        baja=Count('id', filter=Q(estado_tecnico__nombre='Dado de baja')),
        libres=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_LIBRE)),
        en_uso=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_EN_USO)),
        no_disponibles=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_NO_DISPONIBLE)),
    )
    today = timezone.localdate()
    mantenimientos_alerta = MantenimientoPreventivo.objects.select_related(
        "equipo", "responsable"
    ).filter(
        estado=MantenimientoPreventivo.ESTADO_PROGRAMADO,
        fecha_programada__lte=today + timedelta(days=7),
    ).order_by("fecha_programada")[:6]
    repuestos_bajo_minimo = Repuesto.objects.filter(
        activo=True,
        stock_actual__lte=F("stock_minimo"),
    ).order_by("stock_actual", "nombre")[:6]

    paginator = Paginator(equipos_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return {
        'equipos': page_obj,
        'page_obj': page_obj,
        'areas': areas,
        'marcas': Marca.objects.all(),
        'tipos': TipoEquipo.objects.all(),
        'estados': EstadoEquipo.objects.all(),
        'stats': stats,
        'repuestos_bajo_minimo': repuestos_bajo_minimo,
        'repuestos_bajo_minimo_count': Repuesto.objects.filter(activo=True, stock_actual__lte=F("stock_minimo")).count(),
        'mantenimientos_alerta': mantenimientos_alerta,
        'mantenimientos_alerta_count': MantenimientoPreventivo.objects.filter(
            estado=MantenimientoPreventivo.ESTADO_PROGRAMADO,
            fecha_programada__lte=today + timedelta(days=7),
        ).count(),
        'query': q,
        'area_selected': area_id,
        'estado_selected': estado,
        'disponibilidad_selected': disponibilidad,
        'marca_selected': marca_id,
        'tipo_selected': tipo_id,
        'vista_selected': vista,
        'page_querystring': page_querystring(request),
        'export_querystring': inventory_export_querystring(request),
        'total_bajas': Equipo.objects.filter(activo=False).count(),
        'form': form or EquipoForm(),
        'repuesto_form': RepuestoForm(),
        'mantenimiento_form': MantenimientoPreventivoForm(usuarios_queryset=usuarios_mantenimiento_queryset()),
        'can_manage_inventory': can_manage_inventory(request.user),
    }


def equipo_form_error_message(form):
    parts = []
    for field, errors in form.errors.items():
        label = form.fields.get(field).label if field in form.fields else "Error"
        if field == "__all__":
            label = "Error general"
        for error in errors:
            parts.append(f"{label}: {error}")
    return "Corrija los errores en el formulario: " + " ".join(parts) if parts else "Corrija los errores en el formulario."

@login_required
@user_passes_test(can_view_inventory)
def inventario_list(request):
    return render(request, 'inventario/inventario_list.html', get_inventario_context(request))


@login_required
@user_passes_test(can_view_inventory_control)
def inventario_control_operativo(request):
    today = timezone.localdate()
    q_repuesto = request.GET.get("q_repuesto", "").strip()
    q_mantenimiento = request.GET.get("q_mantenimiento", "").strip()
    repuestos = Repuesto.objects.filter(activo=True).order_by("nombre")
    if q_repuesto:
        repuestos = repuestos.filter(
            Q(nombre__icontains=q_repuesto)
            | Q(categoria__icontains=q_repuesto)
            | Q(ubicacion__icontains=q_repuesto)
            | Q(observaciones__icontains=q_repuesto)
        )
    mantenimientos = MantenimientoPreventivo.objects.select_related(
        "equipo", "responsable"
    ).filter(
        estado=MantenimientoPreventivo.ESTADO_PROGRAMADO,
    ).order_by("fecha_programada", "equipo__codigo_equipo")
    if q_mantenimiento:
        mantenimientos = mantenimientos.filter(
            Q(equipo__codigo_equipo__icontains=q_mantenimiento)
            | Q(equipo__nombre_equipo__icontains=q_mantenimiento)
            | Q(responsable__first_name__icontains=q_mantenimiento)
            | Q(responsable__last_name__icontains=q_mantenimiento)
            | Q(estado__icontains=q_mantenimiento)
        )
    repuestos_page = Paginator(repuestos, 10).get_page(request.GET.get("repuestos_page"))
    mantenimientos_page = Paginator(mantenimientos, 10).get_page(request.GET.get("mantenimientos_page"))
    context = {
        "repuestos": repuestos_page,
        "repuestos_page": repuestos_page,
        "repuestos_bajo_minimo_count": Repuesto.objects.filter(activo=True, stock_actual__lte=F("stock_minimo")).count(),
        "mantenimientos": mantenimientos_page,
        "mantenimientos_page": mantenimientos_page,
        "mantenimientos_alerta_count": MantenimientoPreventivo.objects.filter(
            estado=MantenimientoPreventivo.ESTADO_PROGRAMADO,
            fecha_programada__lte=today + timedelta(days=7),
        ).count(),
        "q_repuesto": q_repuesto,
        "q_mantenimiento": q_mantenimiento,
        "repuestos_page_querystring": control_operativo_querystring(request, "repuestos_page"),
        "mantenimientos_page_querystring": control_operativo_querystring(request, "mantenimientos_page"),
        "equipos_mantenimiento": Equipo.objects.filter(activo=True).select_related("area").order_by("codigo_equipo"),
        "repuesto_form": RepuestoForm(),
        "mantenimiento_form": MantenimientoPreventivoForm(usuarios_queryset=usuarios_mantenimiento_queryset()),
        "can_manage_inventory": can_manage_inventory(request.user),
        "can_manage_maintenance": can_manage_inventory(request.user),
        "today": today,
    }
    return render(request, "inventario/control_operativo.html", context)


@login_required
@user_passes_test(can_manage_inventory)
def inventario_export_excel(request):
    equipos = get_filtered_equipos_queryset(request)
    excel_file = generate_excel_inventario(equipos)
    filename = f"inventario_equipos_{timezone.now().strftime('%Y%m%d')}.xlsx"
    registrar_auditoria(
        request,
        "Inventario",
        "descargó Excel de inventario",
        f"El usuario {request.user.get_full_name() or request.user.username} descargó un Excel del inventario con filtros aplicados.",
        None,
    )
    return FileResponse(excel_file, as_attachment=True, filename=filename)


@login_required
@user_passes_test(can_view_inventory)
def inventario_export_pdf(request):
    equipos = get_filtered_equipos_queryset(request)
    equipos_list = list(equipos[:60])
    stats = equipos.aggregate(
        total=Count('id'),
        operativos=Count('id', filter=Q(estado_tecnico__nombre='Operativo')),
        en_revision=Count('id', filter=Q(estado_tecnico__nombre='En revisión')),
        reparacion=Count('id', filter=Q(estado_tecnico__nombre='En reparación')),
        inoperativos=Count('id', filter=Q(estado_tecnico__nombre='Inoperativo')),
        baja=Count('id', filter=Q(estado_tecnico__nombre='Dado de baja')),
        libres=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_LIBRE)),
        en_uso=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_EN_USO)),
        no_disponibles=Count('id', filter=Q(disponibilidad=Equipo.DISPONIBILIDAD_NO_DISPONIBLE)),
    )
    area_id = request.GET.get('area') or ''
    tipo_id = request.GET.get('tipo') or ''
    marca_id = request.GET.get('marca') or ''
    context = {
        'equipos': equipos_list,
        'stats': stats,
        'vista_selected': request.GET.get('vista', 'activos'),
        'query': request.GET.get('q') or 'Sin búsqueda',
        'area_label': Area.objects.filter(pk=area_id).first() if area_id.isdigit() else 'Todas',
        'estado_label': request.GET.get('estado') or 'Todos',
        'disponibilidad_label': dict(Equipo.DISPONIBILIDAD_CHOICES).get(request.GET.get('disponibilidad'), 'Todas'),
        'tipo_label': TipoEquipo.objects.filter(pk=tipo_id).first() if tipo_id.isdigit() else 'Todos',
        'marca_label': Marca.objects.filter(pk=marca_id).first() if marca_id.isdigit() else 'Todas',
        'generado_por': request.user,
        'generado_por_nombre': request.user.get_full_name() or request.user.username,
        'generado_en': timezone.localtime(timezone.now()),
    }
    pdf_file = generate_pdf('inventario/exports/reporte_inventario.html', context)
    if pdf_file:
        registrar_auditoria(
            request,
            "Inventario",
            "descargó PDF de inventario",
            f"El usuario {request.user.get_full_name() or request.user.username} descargó un PDF del inventario con filtros aplicados.",
            None,
        )
        filename = f"inventario_equipos_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(pdf_file, content_type='application/pdf', filename=filename)
    raise Http404("Error al generar el PDF de inventario")


@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def repuesto_crear(request):
    form = RepuestoForm(request.POST)
    if form.is_valid():
        repuesto = form.save()
        registrar_auditoria(
            request,
            "Inventario",
            "registró repuesto",
            f"Se registró el repuesto {repuesto.nombre} con stock {repuesto.stock_actual} y mínimo {repuesto.stock_minimo}.",
            repuesto.id,
        )
        messages.success(request, f"Repuesto {repuesto.nombre} registrado.")
    else:
        messages.error(request, equipo_form_error_message(form))
    return redirect("inventario_control_operativo")


@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def repuesto_actualizar_stock(request, pk):
    repuesto = get_object_or_404(Repuesto, pk=pk, activo=True)
    form = RepuestoStockForm(request.POST)
    if form.is_valid():
        stock_anterior = repuesto.stock_actual
        repuesto.stock_actual = form.cleaned_data["stock_actual"]
        repuesto.save(update_fields=["stock_actual", "actualizado_en"])
        observacion = form.cleaned_data.get("observacion") or "Ajuste operativo de stock."
        registrar_auditoria(
            request,
            "Inventario",
            "actualizó stock de repuesto",
            f"Se actualizó el stock de {repuesto.nombre}: {stock_anterior} -> {repuesto.stock_actual}. Motivo: {observacion}",
            repuesto.id,
        )
        messages.success(request, f"Stock de {repuesto.nombre} actualizado.")
    else:
        messages.error(request, equipo_form_error_message(form))
    return redirect("inventario_control_operativo")


@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def mantenimiento_crear(request):
    form = MantenimientoPreventivoForm(request.POST, usuarios_queryset=usuarios_mantenimiento_queryset())
    if form.is_valid():
        mantenimiento = form.save()
        registrar_auditoria(
            request,
            "Inventario",
            "programó mantenimiento preventivo",
            f"Se programó mantenimiento preventivo para {mantenimiento.equipo.codigo_equipo} el {mantenimiento.fecha_programada}.",
            mantenimiento.id,
        )
        messages.success(request, f"Mantenimiento de {mantenimiento.equipo.codigo_equipo} programado.")
    else:
        messages.error(request, equipo_form_error_message(form))
    return redirect("inventario_control_operativo")


@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def mantenimiento_completar(request, pk):
    mantenimiento = get_object_or_404(MantenimientoPreventivo, pk=pk)
    form = MantenimientoCompletarForm(request.POST)
    if form.is_valid():
        mantenimiento.estado = MantenimientoPreventivo.ESTADO_REALIZADO
        mantenimiento.resultado = form.cleaned_data["resultado"]
        mantenimiento.fecha_realizado = timezone.localdate()
        mantenimiento.full_clean()
        mantenimiento.save(update_fields=["estado", "resultado", "fecha_realizado", "actualizado_en"])
        registrar_auditoria(
            request,
            "Inventario",
            "completó mantenimiento preventivo",
            f"Se completó el mantenimiento preventivo de {mantenimiento.equipo.codigo_equipo}.",
            mantenimiento.id,
        )
        messages.success(request, f"Mantenimiento de {mantenimiento.equipo.codigo_equipo} completado.")
    else:
        messages.error(request, equipo_form_error_message(form))
    return redirect("inventario_control_operativo")


@login_required
@user_passes_test(can_view_inventory)
def equipo_export_pdf(request, pk):
    equipo = get_object_or_404(
        Equipo.objects.select_related('area', 'marca', 'tipo_equipo', 'estado', 'estado_tecnico')
        .prefetch_related('historial_estado__usuario_que_cambio'),
        pk=pk,
    )
    incidencias_relacionadas = (
        equipo.incidencia_set.select_related('creador', 'tecnico_asignado', 'estado')
        .order_by('-fecha_creacion')[:12]
    )
    context = {
        'equipo': equipo,
        'incidencias_relacionadas': incidencias_relacionadas,
        'generado_por': request.user,
        'generado_por_nombre': request.user.get_full_name() or request.user.username,
        'generado_en': timezone.localtime(timezone.now()),
    }
    pdf_file = generate_pdf('inventario/exports/ficha_equipo.html', context)
    if pdf_file:
        registrar_auditoria(
            request,
            "Inventario",
            "descargó PDF de equipo",
            f"El usuario {request.user.get_full_name() or request.user.username} descargó la ficha PDF del equipo {equipo.codigo_equipo}.",
            equipo.id,
        )
        filename = f"equipo_{equipo.codigo_equipo}_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(pdf_file, content_type='application/pdf', filename=filename)
    raise Http404("Error al generar el PDF del equipo")

@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def equipo_crear(request):
    form = EquipoForm(request.POST, request.FILES)
    if form.is_valid():
        equipo = form.save()
        registrar_auditoria(
            request, "Inventario", "creó equipo",
            f"Se registró el nuevo equipo {equipo.codigo_equipo} ({equipo.nombre_equipo}) en el área {equipo.area}.",
            equipo.id
        )
        messages.success(request, f"Equipo {equipo.codigo_equipo} registrado exitosamente.")
        return redirect('inventario_list')
    
    add_form_errors_to_messages(request, form)
    context = get_inventario_context(request, form=form)
    context['show_modal_nuevo'] = True
    return render(request, 'inventario/inventario_list.html', context)

@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def equipo_editar(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk, activo=True)
    form = EquipoForm(request.POST, request.FILES, instance=equipo)
    if form.is_valid():
        area_ant = equipo.area
        nombre_ant = equipo.nombre_equipo
        disponibilidad_ant = equipo.get_disponibilidad_display()
        form.save()
        
        cambios = []
        if area_ant != equipo.area:
            cambios.append(f"Área: {area_ant} -> {equipo.area}")
        if nombre_ant != equipo.nombre_equipo:
            cambios.append(f"Nombre: {nombre_ant} -> {equipo.nombre_equipo}")
        if disponibilidad_ant != equipo.get_disponibilidad_display():
            cambios.append(f"Disponibilidad: {disponibilidad_ant} -> {equipo.get_disponibilidad_display()}")
            if equipo.disponibilidad != Equipo.DISPONIBILIDAD_LIBRE and not equipo.origen_ocupacion:
                equipo.origen_ocupacion = Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA
                equipo.save(update_fields=["origen_ocupacion", "actualizado_en"])
            
        desc = f"Se actualizó el equipo {equipo.codigo_equipo}."
        if cambios:
            desc += " Cambios: " + ", ".join(cambios)
            
        registrar_auditoria(request, "Inventario", "editó equipo", desc, equipo.id)
        messages.success(request, f"Equipo {equipo.codigo_equipo} actualizado.")
        return redirect('inventario_list')
    
    messages.error(request, equipo_form_error_message(form))
    context = get_inventario_context(request, form=form)
    context['show_modal_editar'] = True
    context['equipo_id_error'] = pk
    return render(request, 'inventario/inventario_list.html', context)

@login_required
@user_passes_test(can_view_inventory)
def equipo_detalle(request, pk):
    equipo = get_object_or_404(
        Equipo.objects.select_related('area', 'marca', 'tipo_equipo').prefetch_related('historial_estado__usuario_que_cambio'),
        pk=pk,
    )
    incidencias_relacionadas = (
        equipo.incidencia_set.select_related('creador', 'tecnico_asignado', 'estado')
        .order_by('-fecha_creacion')
    )
    historial_estado_form = EquipoEstadoUpdateForm(current_estado=equipo.estado_tecnico)
    return render(
        request,
        'inventario/equipo_detalle.html',
        {
            'equipo': equipo,
            'incidencias_relacionadas': incidencias_relacionadas,
            'historial_estado_form': historial_estado_form,
            'can_manage_inventory': can_manage_inventory(request.user),
        },
    )


@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def equipo_actualizar_estado(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    form = EquipoEstadoUpdateForm(request.POST, current_estado=equipo.estado_tecnico)
    if form.is_valid():
        historial = registrar_cambio_manual_estado_equipo(
            equipo=equipo,
            nuevo_estado=form.cleaned_data["estado"],
            usuario=request.user,
            observacion=form.cleaned_data["observacion"],
        )
        if historial:
            messages.success(request, f"Estado de {equipo.codigo_equipo} actualizado a {historial.estado_nuevo}.")
        else:
            messages.info(request, "No hubo cambios porque el equipo ya tenía ese estado.")
        return redirect('equipo_detalle', pk=pk)

    messages.error(request, "Debe registrar una observación válida para cambiar el estado del equipo.")
    incidencias_relacionadas = (
        equipo.incidencia_set.select_related('creador', 'tecnico_asignado', 'estado')
        .order_by('-fecha_creacion')
    )
    return render(
        request,
        'inventario/equipo_detalle.html',
        {
            'equipo': equipo,
            'incidencias_relacionadas': incidencias_relacionadas,
            'historial_estado_form': form,
        },
    )

@login_required
@user_passes_test(can_manage_inventory)
@require_POST
def equipo_eliminar_logico(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    motivo = request.POST.get("motivo", "Dado de baja administrativamente.")
    
    estado_baja = EstadoEquipo.objects.filter(nombre="Dado de baja").first()
    if estado_baja:
        registrar_cambio_manual_estado_equipo(
            equipo=equipo,
            nuevo_estado=estado_baja,
            usuario=request.user,
            observacion=motivo
        )
    
    messages.warning(request, f"Equipo {equipo.codigo_equipo} dado de baja del sistema (lógico).")
    from django.urls import reverse
    return redirect(f"{reverse('inventario_list')}?vista=bajas")
