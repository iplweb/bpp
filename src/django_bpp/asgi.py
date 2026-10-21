# mysite/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Te importy muszą biec po get_asgi_application(), żeby AppRegistry
# było zainicjalizowane — liveops.routing importuje ORM modele.
import liveops.routing  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

# liveops.routing binduje ten sam path /asgi/notifications/ co
# channels_broadcast, ale LiveOperationConsumer DZIEDZICZY po
# NotificationsConsumer (nadzbiór: realne powiadomienia przez super() +
# snapshoty liveop.*). To drop-in replacement, więc powiadomienia
# channels_broadcast działają dalej bez zmian.
websocket_urlpatterns = liveops.routing.websocket_urlpatterns

# Aplikacja MCP i jej routing. Import PO get_asgi_application() — mcp_server
# sięga po modele przez klienta w procesie.
from mcp_server.aplikacja import build_application  # noqa: E402
from mcp_server.routing import LifespanMcp, RouterHttp  # noqa: E402

_mcp_app, _mcp_start = build_application()

application = ProtocolTypeRouter(
    {
        "http": RouterHttp(_mcp_app, django_asgi_app, _mcp_start),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
        # ProtocolTypeRouter nie „nie obsługuje" lifespanu — po prostu nie ma
        # dla niego klucza i rzuca ValueError, który uvicorn loguje jako
        # „appears unsupported" i ignoruje. Menedżer sesji MCP nigdy wtedy nie
        # wstaje (spec §2.4, §5.1).
        "lifespan": LifespanMcp(_mcp_start),
    }
)
