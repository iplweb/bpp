from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from notifications_asgi import routing as notifications_asgi_routing

application = ProtocolTypeRouter(
    {
        # (http->django views is added by default)
        "websocket": AuthMiddlewareStack(
            URLRouter(notifications_asgi_routing.websocket_urlpatterns)
        ),
    }
)
