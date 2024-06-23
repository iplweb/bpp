# chat/consumers.py
import json
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from notifications.core import get_channel_name_for_user

from django.utils.functional import cached_property


class NotificationsConsumer(WebsocketConsumer):
    def _channels(self):
        # Kanał dla wszystkich - __all__
        yield "__all__"

        # Kanał wyłącznie dla konkretnego użytkownika
        if self.scope["user"].is_authenticated:

            yield get_channel_name_for_user(self.scope["user"])

            qstr = parse_qs(self.scope["query_string"])
            if b"extraChannels" in qstr:
                for elem in json.loads(qstr[b"extraChannels"][0]):
                    yield str(elem)

    @cached_property
    def channels(self):
        return list(self._channels())

    def subscribe(self):
        for channel in self.channels:
            async_to_sync(self.channel_layer.group_add)(channel, self.channel_name)

    def unsubscribe(self):
        for channel in self.channels:
            async_to_sync(self.channel_layer.group_discard)(channel, self.channel_name)

    def connect(self):
        self.subscribe()
        self.accept()

        from notifications.models import Notification

        Notification.objects.on_connect(self.channels)

    def disconnect(self, close_code):
        self.unsubscribe()

    def chat_message(self, event):
        self.send(text_data=json.dumps(event))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)

        if text_data_json.get("type") == "ack_message":
            from notifications.models import Notification

            try:
                n = Notification.objects.get(id=text_data_json["id"])
            except Notification.DoesNotExist:
                return

            if n.channel_name in self.channels:
                n.acknowledge()
