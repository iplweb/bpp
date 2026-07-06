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

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
