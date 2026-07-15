import pytest
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def redaktor(django_user_model):
    """Użytkownik z uprawnieniami redaktorskimi (grupa „wprowadzanie danych").

    Widoki tej aplikacji mutują dane globalne (usuwanie/przemapowanie źródeł),
    więc wymagają uprawnień redaktorskich — samo zalogowanie nie wystarcza.
    """
    user = django_user_model.objects.create(username="redaktor-przemapuj")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    return user
