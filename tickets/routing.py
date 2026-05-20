from django.urls import path

from .consumers import NotificationConsumer


websocket_urlpatterns = [
    path("ws/notificaciones/", NotificationConsumer.as_asgi()),
]
