from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from auditoria.utils import registrar_auditoria
from .views_utils import is_admin, is_fetch_request, form_errors_to_dict, page_querystring
from ..models import Area
from ..forms.forms_areas import AreaForm

REGISTROS_POR_PAGINA = 10

def render_area_row(request, area):
    return render_to_string(
        "tickets/partials/area_row.html",
        {"area": area},
        request=request,
    )

def get_areas_context(request, creation_form=None, update_form=None):
    areas_list = Area.objects.all().order_by('sede_principal', 'name')
    q = request.GET.get("q")
    if q:
        areas_list = areas_list.filter(name__icontains=q)
    
    sede = request.GET.get("sede")
    if sede:
        areas_list = areas_list.filter(sede_principal=sede)

    page_obj = Paginator(areas_list, REGISTROS_POR_PAGINA).get_page(request.GET.get("page"))
    
    # Get unique sedes for filter
    sedes = [choice[0] for choice in Area.SEDE_CHOICES]

    return {
        "areas": page_obj,
        "page_obj": page_obj,
        "sedes": sedes,
        "query": q,
        "page_querystring": page_querystring(request),
        "creation_form": creation_form or AreaForm(),
        "update_form": update_form or AreaForm(),
    }

@login_required
@user_passes_test(is_admin)
def areas_list(request):
    return render(request, "tickets/areas.html", get_areas_context(request))

@login_required
@user_passes_test(is_admin)
@require_POST
def area_crear(request):
    form = AreaForm(request.POST)
    if form.is_valid():
        area = form.save()
        registrar_auditoria(
            request,
            "Áreas",
            "creó área",
            f"El administrador {request.user.username} creó el área '{area.name}' en la sede '{area.sede_principal}'.",
            area.id,
        )
        message = f"Área '{area.name}' creada exitosamente."
        if is_fetch_request(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "area_id": area.pk,
                    "row_html": render_area_row(request, area),
                },
                status=201,
            )
        messages.success(request, message)
        return redirect("areas_list")

    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": False,
                "message": "No se pudo crear el área. Verifique los campos.",
                "errors": form_errors_to_dict(form),
            },
            status=400,
        )

    messages.error(request, "No se pudo crear el área. Verifique los campos.")
    context = get_areas_context(request, creation_form=form)
    context["show_modal_nuevo"] = True
    return render(request, "tickets/areas.html", context)

@login_required
@user_passes_test(is_admin)
@require_POST
def area_editar(request, pk):
    area = get_object_or_404(Area, pk=pk)
    before_name = area.name
    before_sede = area.sede_principal
    form = AreaForm(request.POST, instance=area)
    if form.is_valid():
        area = form.save()
        registrar_auditoria(
            request,
            "Áreas",
            "editó área",
            f"El administrador {request.user.username} editó el área '{before_name}' (Sede: {before_sede}) "
            f"a '{area.name}' (Sede: {area.sede_principal}).",
            area.id,
        )
        message = f"Área '{area.name}' actualizada exitosamente."
        if is_fetch_request(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "area_id": area.pk,
                    "row_html": render_area_row(request, area),
                }
            )
        messages.success(request, message)
        return redirect("areas_list")

    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": False,
                "message": "No se pudo actualizar el área.",
                "errors": form_errors_to_dict(form),
            },
            status=400,
        )

    messages.error(request, "No se pudo actualizar el área.")
    context = get_areas_context(request, update_form=form)
    context["show_modal_editar"] = True
    context["area_id_error"] = pk
    return render(request, "tickets/areas.html", context)

@login_required
@user_passes_test(is_admin)
@require_POST
def area_eliminar(request, pk):
    area = get_object_or_404(Area, pk=pk)
    # Verificar si existen usuarios asignados al área
    if area.customuser_set.exists():
        msg = "No se puede eliminar el área porque tiene usuarios asignados."
        if is_fetch_request(request):
            return JsonResponse({"success": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("areas_list")
        
    # Verificar si existen incidencias asignadas al área
    if area.incidencia_set.exists():
        msg = "No se puede eliminar el área porque tiene incidencias registradas."
        if is_fetch_request(request):
            return JsonResponse({"success": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("areas_list")

    name = area.name
    sede = area.sede_principal
    area.delete()
    registrar_auditoria(
        request,
        "Áreas",
        "eliminó área",
        f"El administrador {request.user.username} eliminó el área '{name}' de la sede '{sede}'.",
        pk,
    )
    message = f"Área '{name}' eliminada correctamente."
    if is_fetch_request(request):
        return JsonResponse({"success": True, "message": message})
    messages.success(request, message)
    return redirect("areas_list")
