import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.serializers import JSONSerializer
from django.test import RequestFactory


@pytest.mark.django_db
def test_password_policies_session_survives_json_serializer(test_user, monkeypatch):
    """Regression guard for SESSION_SERIALIZER=JSONSerializer.

    django-password-policies-iplweb >= 0.8.6 stores session bookkeeping
    as ISO strings, not raw datetime objects, so the values written by
    PasswordChangeMiddleware must round-trip through Django's
    JSONSerializer.  If this ever fails, DO NOT switch back to Pickle
    (RCE risk) -- fix the dependency instead.
    """
    from password_policies.conf import settings as password_settings
    from password_policies.middleware import PasswordChangeMiddleware

    # Rotacja jest domyślnie wyłączona, a wtedy middleware nic nie zapisuje.
    monkeypatch.setattr(
        password_settings, "PASSWORD_DURATION_SECONDS", 30 * 24 * 60 * 60
    )

    request = RequestFactory().get("/")
    request.session = SessionStore()
    request.user = test_user

    PasswordChangeMiddleware(lambda r: None).process_request(request)

    serializer = JSONSerializer()
    payload = serializer.dumps(dict(request.session))
    restored = serializer.loads(payload)

    assert "_password_policies_last_checked" in restored
    assert isinstance(restored["_password_policies_last_checked"], str)
