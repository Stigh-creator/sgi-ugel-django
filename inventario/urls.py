from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventario_list, name='inventario_list'),
    path('exportar/excel/', views.inventario_export_excel, name='inventario_export_excel'),
    path('exportar/pdf/', views.inventario_export_pdf, name='inventario_export_pdf'),
    path('crear/', views.equipo_crear, name='equipo_crear'),
    path('<int:pk>/pdf/', views.equipo_export_pdf, name='equipo_export_pdf'),
    path('<int:pk>/editar/', views.equipo_editar, name='equipo_editar'),
    path('<int:pk>/detalle/', views.equipo_detalle, name='equipo_detalle'),
    path('<int:pk>/estado/', views.equipo_actualizar_estado, name='equipo_actualizar_estado'),
    path('<int:pk>/eliminar/', views.equipo_eliminar_logico, name='equipo_eliminar'),
]
