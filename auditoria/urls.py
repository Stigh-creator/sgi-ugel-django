from django.urls import path
from . import views

urlpatterns = [
    path('', views.auditoria_dashboard, name='auditoria_index'),
    path('exportar/pdf/', views.auditoria_export_pdf, name='auditoria_export_pdf'),
]
