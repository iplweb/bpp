import pytest
from django.test import Client

TEST_USERNAME = "user"
TEST_PASSWORD = "foo"


@pytest.mark.django_db
def test_password_policies_session_survives_json_serializer(
    settings, test_user
):
    """Regression guard for SESSION_SERIALIZER=JSONSerializer.

    django-password-policies-iplweb >= 0.8.6 stores its session bookkeeping
    as ISO strings, not raw datetime objects, so JSONSerializer must be
    able to round-trip an authenticated GET through PasswordChangeMiddleware
    without raising TypeError. If this test ever fails, either the dep was
    downgraded below 0.8.6 or upstream regressed to writing non-JSON types
    into request.session — in which case DO NOT switch back to Pickle
    (RCE risk), fix the dependency instead.
    """
    settings.SESSION_SERIALIZER = (
        "django.contrib.sessions.serializers.JSONSerializer"
    )
    client = Client()
    assert client.login(username=TEST_USERNAME, password=TEST_PASSWORD)

    response = client.get("/")
    assert response.status_code in (200, 302)

    session = client.session
    assert "_password_policies_last_checked" in session
    assert isinstance(session["_password_policies_last_checked"], str)
