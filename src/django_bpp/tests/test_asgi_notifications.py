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

``on_connect`` (replay z bazy) jest zamockowany, więc NIE odpytujemy tabel
notyfikacji, a ``InMemoryChannelLayer`` trzyma Redisa z daleka — exerciseujemy
wyłącznie bramkę auth + accept/close. Testy są jednak ``@pytest.mark.django_db``:
channels owija sync-consumera w ``DatabaseSyncToAsync``, który woła
``close_old_connections()`` (channels/db.py) wokół handlera. To iteruje
zainicjalizowane połączenia i robi ``ensure_connection()``. Gdy wcześniejszy
test w procesie zainicjalizował połączenie w współdzielonym wątku sync-executora,
pytest-django blokuje ten dostęp dla testu bez marka → ``RuntimeError: Database
access not allowed`` (flaky zależny od kolejności; w izolacji przechodzi, bo
połączenie nie jest zainicjalizowane). Mark zezwala na sam cykl połączenia
(bez realnych zapytań do tabel).

Korutynę ``WebsocketCommunicatora`` (repo nie ma ``pytest-asyncio``) odpalamy
w dedykowanym wątku przez ``asyncio.run``. Wcześniej był tu ``async_to_sync``,
ale on celowo rzuca ``RuntimeError: You cannot use AsyncToSync in the same
thread as an async event loop`` gdy w bieżącym wątku już biegnie pętla — a
zdarza się to, gdy wcześniejszy test w tym samym shardzie ``pytest-split``
zostawił działającą pętlę (kolejny flaky zależny od kolejności). Osobny wątek
ma własną, świeżą pętlę i jest odporny na stan pętli wątku wołającego.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
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

    # Dedykowany wątek + świeża pętla — odporne na pętlę asyncio ewentualnie
    # zostawioną w wątku wołającym przez inny test (flake zależny od kolejności).
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(_run())).result()


def test_bpp_enables_anonymous_notifications():
    """Kontrakt z frontem: BPP ma włączone anonimowe notyfikacje."""
    assert settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS is True


@pytest.mark.django_db
def test_anonymous_user_can_connect(settings, mocker):
    """Z flagą BPP (True) anonim nawiązuje WS — handshake zaakceptowany."""
    settings.CHANNEL_LAYERS = INMEMORY_LAYER
    settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS = True
    mocker.patch("channels_broadcast.models.Notification.objects.on_connect")

    assert _connect_as_anonymous() is True


@pytest.mark.django_db
def test_anonymous_rejected_when_flag_disabled(settings, mocker):
    """Objaw sprzed fixu: bez flagi anonim jest odrzucany (close przed accept)."""
    settings.CHANNEL_LAYERS = INMEMORY_LAYER
    settings.CHANNELS_BROADCAST_ENABLE_ANONYMOUS = False
    mocker.patch("channels_broadcast.models.Notification.objects.on_connect")

    assert _connect_as_anonymous() is False
