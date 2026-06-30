"""
ASGI WebSocket URL patterns for live_operations.

Include these in your project's ASGI routing instead of (or in addition to)
channels_broadcast's own routing. LiveOperationConsumer is a drop-in
replacement for NotificationsConsumer at the same path.

Usage in your ASGI app::

    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from live_operations.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""
from django.urls import path

from live_operations.consumers import LiveOperationConsumer

websocket_urlpatterns = [
    path("asgi/notifications/", LiveOperationConsumer.as_asgi()),
]
