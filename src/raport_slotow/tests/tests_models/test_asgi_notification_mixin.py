import pytest

from raport_slotow.models.asgi_notification_mixin import ASGINotificationMixin


@pytest.fixture
def fake_rekord():
    class FakeRekord(ASGINotificationMixin):
        pk = 500

    return FakeRekord()


def test_ASGINotificationMixin_asgi_channel_name(fake_rekord):
    assert fake_rekord.asgi_channel_name == "500"


def test_ASGINotificationMixin_send_notification(fake_rekord, mocker):
    from notifications import core

    mocker.patch("notifications.core.send_notification")
    fake_rekord.send_notification("msg")
    core.send_notification.assert_called_once_with("500", 20, "msg")


def test_ASGINotificationMixin_send_progress(fake_rekord, mocker):
    from notifications import core

    mocker.patch("notifications.core._send")
    fake_rekord.send_progress(20)
    core._send.assert_called_once()
