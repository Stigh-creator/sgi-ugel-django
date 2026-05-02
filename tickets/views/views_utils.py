from django.contrib import messages
from django.http import HttpResponse

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "administrador")

def is_fetch_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def add_form_errors_to_messages(request, form):
    for field, errors in form.errors.items():
        label = form.fields.get(field).label if field in form.fields else None
        prefix = label or "Error"
        if field == "__all__":
            prefix = "Error"
        for error in errors:
            messages.error(request, f"{prefix}: {error}")

def form_errors_to_dict(form):
    return {
        field: [str(error) for error in errors]
        for field, errors in form.errors.items()
    }

def page_querystring(request):
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""

def HttpResponseClientRefresh():
    response = HttpResponse()
    response['HX-Refresh'] = 'true'
    return response
