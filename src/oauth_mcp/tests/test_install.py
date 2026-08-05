import pytest
from django.apps import apps


def test_apki_zaladowane():
    assert apps.is_installed("oauth2_provider")
    assert apps.is_installed("oauth_mcp")


@pytest.mark.django_db
def test_modele_dot_dostepne():
    from oauth2_provider.models import get_access_token_model

    AccessToken = get_access_token_model()
    assert AccessToken.objects.count() == 0
