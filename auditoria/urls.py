from django.urls import path
from . import views

urlpatterns = [
    path('', views.auditoria_dashboard, name='auditoria_index'),
]
