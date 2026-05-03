"""Testy klas pomocniczych admin.py: RequestNotifier, ResultNotifier,
ReadonlyAdminMixin."""

import pytest
from django.contrib.messages import get_messages

from .conftest import middleware


@pytest.mark.django_db
def test_request_notifier_info_adds_message(rf):
    """Test that RequestNotifier.info adds info message to request."""
    from rozbieznosci_dyscyplin.admin import RequestNotifier

    req = rf.get("/")
    with middleware(req):
        notifier = RequestNotifier(req)
        notifier.info("Test info message")
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert msgs[0].message == "Test info message"


@pytest.mark.django_db
def test_request_notifier_warning_adds_message(rf):
    """Test that RequestNotifier.warning adds warning message to request."""
    from rozbieznosci_dyscyplin.admin import RequestNotifier

    req = rf.get("/")
    with middleware(req):
        notifier = RequestNotifier(req)
        notifier.warning("Test warning message")
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert msgs[0].message == "Test warning message"


def test_result_notifier_info_appends_to_buffer():
    """Test that ResultNotifier.info appends message to buffer."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier

    notifier = ResultNotifier()
    notifier.info("Message 1")
    notifier.info("Message 2")

    assert notifier.retbuf == ["Message 1", "Message 2"]


def test_result_notifier_warning_appends_to_buffer():
    """Test that ResultNotifier.warning appends message to buffer."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier

    notifier = ResultNotifier()
    notifier.warning("Warning 1")
    notifier.warning("Warning 2")

    assert notifier.retbuf == ["Warning 1", "Warning 2"]


def test_readonly_admin_mixin_has_no_delete_permission():
    """Test that ReadonlyAdminMixin returns False for delete permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_delete_permission(None) is False
    assert admin.has_delete_permission(None, obj="something") is False


def test_readonly_admin_mixin_has_no_add_permission():
    """Test that ReadonlyAdminMixin returns False for add permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_add_permission(None) is False


def test_readonly_admin_mixin_has_no_change_permission():
    """Test that ReadonlyAdminMixin returns False for change permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_change_permission(None) is False
    assert admin.has_change_permission(None, obj="something") is False
