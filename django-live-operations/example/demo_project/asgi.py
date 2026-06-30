"""
ASGI config for demo_project.

Routing:
  http      → Django ASGI app
  websocket → AllowedHostsOriginValidator
               → AuthMiddlewareStack
                 → URLRouter([path("asgi/notifications/", LiveOperationConsumer)])

LiveOperationConsumer extends channels_broadcast.NotificationsConsumer,
so the same path handles both channels_broadcast token subscription and
liveop snapshot-on-connect (§19.1).
"""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

from live_operations.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo_project.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
