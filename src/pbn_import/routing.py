"""WebSocket routing for PBN import"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/pbn-import/session/(?P<session_id>\w+)/$",
        consumers.ImportProgressConsumer.as_asgi(),
    ),
]
