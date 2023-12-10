import pytest
from django.apps import apps
from django.core import mail
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.skipif(
    apps.is_installed("microsoft_auth"), reason="działa bez django_microsoft_auth"
)
def test_password_reset(webtest_app, normal_django_user):
    EMAIL = "foo@bar.pl"
    normal_django_user.email = EMAIL
    normal_django_user.save()

    url = reverse("password_reset")
    page = webtest_app.get(url)  # noqa
    page.forms[0]["email"] = EMAIL
    page = page.forms[0].submit().maybe_follow()

    assert page.status_code == 200
    assert len(mail.outbox) == 1
