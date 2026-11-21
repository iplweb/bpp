import pytest
from django.core import signing
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from model_bakery import baker

from bpp.models import BppUser

pytestmark = pytest.mark.django_db


def _reset_url(user):
    # Same signing scheme as password_policies' PasswordResetForm.save().
    _, timestamp, signature = signing.TimestampSigner().sign(user.password).split(":")
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return reverse("password_reset_confirm", args=(uid, timestamp, signature))


def test_password_reset_confirm_has_password_manager_hints(client):
    # Bitwarden (and other password managers) only offer a generated password
    # when the new-password fields carry autocomplete hints.
    user = baker.make(BppUser)
    user.set_password("wrzos-kaktus-lipa-7")  # pragma: allowlist secret
    user.save()

    response = client.get(_reset_url(user))

    html = response.content.decode()
    assert response.status_code == 200
    assert response.context["validlink"]
    assert html.count('autocomplete="new-password"') == 2
    assert 'autocomplete="username"' in html
    assert f'value="{user.get_username()}"' in html
