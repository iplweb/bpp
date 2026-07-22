import pytest
from oauth2_provider.models import get_access_token_model


@pytest.mark.django_db
def test_zmiana_hasla_kasuje_tokeny(access_token):
    user, tok = access_token()
    AccessToken = get_access_token_model()
    assert AccessToken.objects.filter(user=user).exists()
    user.set_password("nowe-haslo-123")
    user.save()
    assert not AccessToken.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_dezaktywacja_kasuje_tokeny(access_token):
    user, tok = access_token()
    AccessToken = get_access_token_model()
    user.is_active = False
    user.save()
    assert not AccessToken.objects.filter(user=user).exists()
