# mysite/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

import pbn_import.routing

# liveops.routing rejestruje LiveOperationConsumer na tej samej sciezce
# (/asgi/notifications/) co channels_broadcast.NotificationsConsumer —
# jest jego drop-in nadzbiorem (dorzuca snapshot-on-connect dla kanalow
# liveop.*). Zastepuje channels_broadcast.routing.
import liveops.routing

websocket_urlpatterns = (
    liveops.routing.websocket_urlpatterns + pbn_import.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
