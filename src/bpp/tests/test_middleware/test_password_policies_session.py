import pytest
from django.conf import settings as django_settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.serializers import JSONSerializer
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import path


def _password_change_stub(request):
    return HttpResponse()


# PasswordChangeMiddleware calls reverse("password_change") unconditionally;
# when microsoft_auth is importable, settings/base.py removes password_policies
# from INSTALLED_APPS and the project's urlconf does not register that name.
urlpatterns = [
    path("password_change/", _password_change_stub, name="password_change"),
    path("", lambda request: HttpResponse(), name="root"),
]


def _installed_apps_with_password_policies():
    apps = list(django_settings.INSTALLED_APPS)
    if "password_policies" not in apps:
        apps.append("password_policies")
    return apps


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=_installed_apps_with_password_policies(),
)
def test_password_policies_session_survives_json_serializer(test_user):
    """Regression guard for SESSION_SERIALIZER=JSONSerializer.

    django-password-policies-iplweb >= 0.8.6 stores session bookkeeping
    as ISO strings, not raw datetime objects, so the values written by
    PasswordChangeMiddleware must round-trip through Django's
    JSONSerializer.  If this ever fails, DO NOT switch back to Pickle
    (RCE risk) -- fix the dependency instead.
    """
    from password_policies.middleware import PasswordChangeMiddleware

    request = RequestFactory().get("/")
    request.session = SessionStore()
    request.user = test_user

    PasswordChangeMiddleware(lambda r: None).process_request(request)

    serializer = JSONSerializer()
    payload = serializer.dumps(dict(request.session))
    restored = serializer.loads(payload)

    assert "_password_policies_last_checked" in restored
    assert isinstance(restored["_password_policies_last_checked"], str)
