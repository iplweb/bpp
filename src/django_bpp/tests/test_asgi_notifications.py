"""Regresja: anonimowy klient musi móc nawiązać WebSocket /asgi/notifications/.

Przejście notyfikacji z lokalnego ``src/notifications/`` na pakiet
``django-channels-broadcast`` (refactor f6e0fa6cf) wprowadziło bramkę w
``NotificationsConsumer.connect()``: anonim jest odrzucany (``self.close()``
PRZED ``self.accept()``) gdy ``CHANNELS_BROADCAST_ENABLE_ANONYMOUS`` jest
wyłączone (domyślna wartość pakietu to ``False``). uvicorn zwraca wtedy HTTP 403
na handshake, a przeglądarka raportuje ``NS_ERROR_WEBSOCKET_CONNECTION_REFUSED``.

Stary lokalny consumer akceptował połączenie bezwarunkowo, więc po przepięciu na
pakiet zewnętrzny anonimowy front przestał się łączyć. BPP ustawia flagę na
``True`` (``settings/base.py``), żeby przywrócić poprzednie zachowanie — ten
plik to przypina, żeby ktoś przypadkiem nie zdjął/odwrócił ustawienia.

Test jest celowo hermetyczny: ``on_connect`` (replay z bazy) jest zamockowany,
więc nie potrzebujemy DB ani Redisa — exerciseujemy wyłącznie bramkę
auth + accept/close na ``InMemoryChannelLayer``. ``async_to_sync`` odpala
asynchroniczny ``WebsocketCommunicator`` w syncowym teście (repo nie ma
``pytest-asyncio``).
"""

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from channels_broadcast.consumers import NotificationsConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

PATH = "/asgi/notifications/"
INMEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def _connect_as_anonymous():
    """Otwórz WS jako anonim i zwróć, czy handshake został zaakceptowany."""

    async def _run():
        communicator = WebsocketCommunicator(NotificationsConsumer.as_asgi(), PATH)
        communicator.scope["user"] = AnonymousUser()
        connected, _ = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected

    return async_to_sync(_run)()


def test_bpp_enables_anonymous_notifications():
    """Kontrakt z frontem: BPP ma włączone anonimowe notyfikacje."""
    assert settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS is True


def test_anonymous_user_can_connect(settings, mocker):
    """Z flagą BPP (True) anonim nawiązuje WS — handshake zaakceptowany."""
    settings.CHANNEL_LAYERS = INMEMORY_LAYER
    settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS = True
    mocker.patch("channels_broadcast.models.Notification.objects.on_connect")

    assert _connect_as_anonymous() is True


def test_anonymous_rejected_when_flag_disabled(settings, mocker):
    """Objaw sprzed fixu: bez flagi anonim jest odrzucany (close przed accept)."""
    settings.CHANNEL_LAYERS = INMEMORY_LAYER
    settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS = False
    mocker.patch("channels_broadcast.models.Notification.objects.on_connect")

    assert _connect_as_anonymous() is False
