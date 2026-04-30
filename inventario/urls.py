from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventario_list, name='inventario_list'),
    path('crear/', views.equipo_crear, name='equipo_crear'),
    path('<int:pk>/editar/', views.equipo_editar, name='equipo_editar'),
    path('<int:pk>/detalle/', views.equipo_detalle, name='equipo_detalle'),
    path('<int:pk>/estado/', views.equipo_actualizar_estado, name='equipo_actualizar_estado'),
    path('<int:pk>/eliminar/', views.equipo_eliminar_logico, name='equipo_eliminar'),
]
