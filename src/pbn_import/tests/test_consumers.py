"""Tests for PBN import WebSocket consumer payloads."""

import concurrent.futures
import datetime
import json
from unittest.mock import AsyncMock

import pytest
from asgiref.sync import async_to_sync as _asgiref_async_to_sync
from django.utils import timezone
from model_bakery import baker

from pbn_import.consumers import ImportProgressConsumer
from pbn_import.models import ImportLog, ImportSession


def async_to_sync(method):
    """``asgiref.async_to_sync`` odporny na przeciekły działający event loop.

    Te testy są SYNC (``def test_...``) i wołają korutyny konsumera przez
    ``async_to_sync``. ``asgiref`` odmawia jednak, gdy wątek wołającego ma już
    DZIAŁAJĄCY event loop ("You cannot use AsyncToSync in the same thread as an
    async event loop"). Na sharded CI tak właśnie bywa: wcześniejszy test async
    w tym samym shardzie zostawia działający loop w wątku workera, więc kolejne
    ``async_to_sync`` tu wywalają się — deterministycznie zależnie od podziału na
    shardy (lokalnie, w izolacji, nie reprodukuje się).

    Naprawa: wykonujemy wywołanie w ŚWIEŻYM wątku, który z definicji nie ma
    działającego loopa — więc ``async_to_sync`` zawsze startuje własny. Sygnatura
    jest drop-in (zwraca callable przyjmujący args/kwargs korutyny), więc miejsca
    wywołań pozostają bez zmian. Lokalnie (bez przecieku) zachowanie identyczne.
    """

    def caller(*args, **kwargs):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                lambda: _asgiref_async_to_sync(method)(*args, **kwargs)
            )
            return future.result()

    return caller


def make_consumer(session_id, user):
    consumer = ImportProgressConsumer()
    consumer.session_id = session_id
    consumer.room_group_name = f"import_{session_id}"
    consumer.scope = {
        "url_route": {"kwargs": {"session_id": session_id}},
        "user": user,
    }
    consumer.channel_name = "test-channel"
    consumer.channel_layer = AsyncMock()
    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()
    consumer.send = AsyncMock()
    return consumer


@pytest.mark.django_db(transaction=True)
def test_connect_accepts_owner_and_sends_initial_status(django_user_model):
    user = baker.make(django_user_model)
    session = baker.make(
        ImportSession,
        user=user,
        status="running",
        current_step="source_import",
        current_step_progress=25,
        completed_steps=1,
        total_steps=4,
    )
    consumer = make_consumer(session.pk, user)

    async_to_sync(consumer.connect)()

    consumer.channel_layer.group_add.assert_awaited_once_with(
        f"import_{session.pk}", "test-channel"
    )
    consumer.accept.assert_awaited_once_with()
    sent_payloads = [
        json.loads(call.kwargs["text_data"]) for call in consumer.send.await_args_list
    ]
    assert sent_payloads[0]["type"] == "connection"
    assert sent_payloads[1]["type"] == "status_update"
    assert sent_payloads[1]["status"]["status"] == "running"
    assert sent_payloads[1]["status"]["current_step"] == "source_import"
    assert sent_payloads[1]["status"]["progress"] == session.overall_progress
    assert sent_payloads[1]["status"]["completed_steps"] == 1
    assert sent_payloads[1]["status"]["total_steps"] == 4
    assert sent_payloads[1]["status"]["duration"]


@pytest.mark.django_db(transaction=True)
def test_connect_closes_for_unauthenticated_user(django_user_model):
    owner = baker.make(django_user_model)
    session = baker.make(ImportSession, user=owner)
    anonymous = type("Anonymous", (), {"is_authenticated": False})()
    consumer = make_consumer(session.pk, anonymous)

    async_to_sync(consumer.connect)()

    consumer.close.assert_awaited_once_with()
    consumer.accept.assert_not_awaited()


@pytest.mark.django_db(transaction=True)
def test_staff_user_can_view_foreign_session(django_user_model):
    owner = baker.make(django_user_model)
    staff = baker.make(django_user_model, is_staff=True)
    session = baker.make(ImportSession, user=owner)
    consumer = make_consumer(session.pk, staff)

    assert async_to_sync(consumer.has_permission)() is True


@pytest.mark.django_db(transaction=True)
def test_has_permission_false_for_missing_session(django_user_model):
    user = baker.make(django_user_model)
    consumer = make_consumer(999_999, user)

    assert async_to_sync(consumer.has_permission)() is False


@pytest.mark.django_db(transaction=True)
def test_get_recent_logs_returns_oldest_first(django_user_model):
    user = baker.make(django_user_model)
    session = baker.make(ImportSession, user=user)
    older = baker.make(ImportLog, session=session, level="info", message="older")
    newer = baker.make(ImportLog, session=session, level="warning", message="newer")
    now = timezone.now()
    ImportLog.objects.filter(pk=older.pk).update(
        timestamp=now - datetime.timedelta(minutes=1)
    )
    ImportLog.objects.filter(pk=newer.pk).update(timestamp=now)
    consumer = make_consumer(session.pk, user)

    logs = async_to_sync(consumer.get_recent_logs)(limit=2)

    assert [log["message"] for log in logs] == [older.message, newer.message]
    assert logs[0]["level"] == "info"
    assert "timestamp" in logs[0]


def test_receive_ping_status_and_logs_requests():
    consumer = make_consumer(1, user=object())
    consumer.send_current_status = AsyncMock()
    consumer.send_recent_logs = AsyncMock()

    async_to_sync(consumer.receive)(
        text_data=json.dumps({"type": "ping", "timestamp": "t1"})
    )
    async_to_sync(consumer.receive)(text_data=json.dumps({"type": "request_status"}))
    async_to_sync(consumer.receive)(text_data=json.dumps({"type": "request_logs"}))

    assert json.loads(consumer.send.await_args.kwargs["text_data"]) == {
        "type": "pong",
        "timestamp": "t1",
    }
    consumer.send_current_status.assert_awaited_once_with()
    consumer.send_recent_logs.assert_awaited_once_with()


def test_event_handlers_serialize_payloads():
    consumer = make_consumer(1, user=object())

    async_to_sync(consumer.import_update)({"data": {"progress": 10}})
    async_to_sync(consumer.progress_update)(
        {"progress": 50, "current_step": "step", "message": "msg"}
    )
    async_to_sync(consumer.log_entry)(
        {
            "timestamp": "2026-06-05T10:00:00",
            "level": "info",
            "step": "source_import",
            "message": "done",
        }
    )
    async_to_sync(consumer.status_change)(
        {"old_status": "running", "new_status": "completed", "message": "ok"}
    )
    async_to_sync(consumer.statistics_update)({"statistics": {"x": 1}})
    async_to_sync(consumer.completion_notification)(
        {"success": True, "message": "completed"}
    )

    payloads = [
        json.loads(call.kwargs["text_data"]) for call in consumer.send.await_args_list
    ]
    assert payloads == [
        {"type": "import_update", "data": {"progress": 10}},
        {
            "type": "progress_update",
            "progress": 50,
            "current_step": "step",
            "message": "msg",
        },
        {
            "type": "log_entry",
            "log": {
                "timestamp": "2026-06-05T10:00:00",
                "level": "info",
                "step": "source_import",
                "message": "done",
            },
        },
        {
            "type": "status_change",
            "old_status": "running",
            "new_status": "completed",
            "message": "ok",
        },
        {"type": "statistics_update", "statistics": {"x": 1}},
        {"type": "completion", "success": True, "message": "completed"},
    ]


def test_disconnect_removes_channel_from_group():
    consumer = make_consumer(123, user=object())
    consumer.room_group_name = "import_123"

    async_to_sync(consumer.disconnect)(1000)

    consumer.channel_layer.group_discard.assert_awaited_once_with(
        "import_123", "test-channel"
    )
