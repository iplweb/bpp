import pytest
from django.core.exceptions import ValidationError
from model_mommy import mommy

from bpp.models import Uczelnia


def test_Uczelnia_clean_pbn_biezaco_tak_integracja_nie(uczelnia):
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_integracja = False

    with pytest.raises(ValidationError, match="nie używasz integracji"):
        uczelnia.clean()


@pytest.mark.django_db
def test_Uczelnia_clean_integracja(uczelnia, mocker):
    uczelnia.pbn_integracja = True
    uczelnia.pbn_app_token = uczelnia.pbn_app_name = "hej"

    pbn_client = mocker.Mock()
    pbn_client.return_value.get_languages.side_effect = KeyError("foo")

    uczelnia.pbn_client = pbn_client

    with pytest.raises(ValidationError, match="Nie można pobrać"):
        uczelnia.clean()


@pytest.mark.django_db
def test_Uczelnia_pbn_client():
    uczelnia = mommy.make(Uczelnia)

    uczelnia.pbn_app_token = uczelnia.pbn_api_root = uczelnia.pbn_app_name = None

    if uczelnia.pbn_app_name is not None:
        raise Exception("x")

    with pytest.raises(AssertionError, match="nazwy aplikacji"):
        uczelnia.pbn_client()

    uczelnia.pbn_app_name = "foo"

    with pytest.raises(AssertionError, match="tokena aplikacji"):
        uczelnia.pbn_client()

    uczelnia.pbn_app_token = "foo"

    with pytest.raises(AssertionError, match="adresu URL"):
        uczelnia.pbn_client()

    uczelnia.pbn_api_root = "foo"

    assert uczelnia.pbn_client()
