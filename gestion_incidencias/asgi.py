import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import tickets.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_incidencias.settings')
os.environ['GIO_USE_VFS'] = 'local'

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            tickets.routing.websocket_urlpatterns
        )
    ),
})
