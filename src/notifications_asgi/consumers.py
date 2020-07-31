# chat/consumers.py
import json
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.generic.websocket import WebsocketConsumer


class NotificationsConsumer(WebsocketConsumer):
    def connect(self):
        # print(f"Podlaczyl sie {self.channel_name}, uzytkownik {self.scope['user']}")
        async_to_sync(self.channel_layer.group_add)("public", self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        # print(f"Rozlaczyl sie {self.channel_name}")
        async_to_sync(self.channel_layer.group_discard)("public", self.channel_name)

    def chat_message(self, event):
        XXX TODO:
        - wysyłanie kluczy takich jak: closeURL, eventClass czy coś w tym stylu, tekst, url
        - typ zdarzenia: href też powinien być obsługiwany

        message = event["message"]
        print(f"Chat_message {message}, event {event}")
        # Send message to WebSocket
        self.send(text_data=json.dumps({"message": message}))

    def chat_Xmessage(self, event):
        print("XMESSAGE")
