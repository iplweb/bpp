# chat/routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"asgi/notifications/$", consumers.NotificationsConsumer.as_asgi()),
]
