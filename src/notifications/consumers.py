# chat/consumers.py
import json
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.generic.websocket import WebsocketConsumer


class NotificationsConsumer(WebsocketConsumer):
    def get_channels(self):
        # Kanał dla wszystkich - __all__
        # Kanał wyłącznie dla konkretnego użytkownika
        yield "__all__"
        if self.scope["user"].is_authenticated:
            yield self.scope["user"].username

    def subscribe(self):
        for channel in self.get_channels():
            async_to_sync(self.channel_layer.group_add)(channel, self.channel_name)

    def unsubscribe(self):
        for channel in self.get_channels():
            async_to_sync(self.channel_layer.group_discard)(channel, self.channel_name)

    def connect(self):
        self.subscribe()
        self.accept()
        self.send_channel_name()

    def disconnect(self, close_code):
        self.unsubscribe()

    def send_channel_name(self):
        self.send(text_data=json.dumps({"channel_name": self.channel_name}))

    def chat_message(self, event):
        # print(f"Chat_message event {event}")
        self.send(text_data=json.dumps(event))
