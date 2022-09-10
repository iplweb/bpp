import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from model_bakery import baker

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

    orig = uczelnia.pbn_client

    uczelnia.pbn_client = pbn_client

    with pytest.raises(ValidationError, match="Nie można pobrać"):
        uczelnia.clean()

    uczelnia.pbn_client = orig


@pytest.mark.django_db
def test_Uczelnia_pbn_client():
    uczelnia = baker.make(
        Uczelnia,
        nazwa="Testowa uczelnia",
        skrot="TU",
        pbn_app_name=None,
        pbn_app_token=None,
    )

    uczelnia.pbn_app_name = None
    uczelnia.save()

    uczelnia.refresh_from_db()

    try:
        res = uczelnia.pbn_client()
        raise Exception(
            f"This should not happen {uczelnia.pbn_app_name} {uczelnia} {uczelnia.pbn_client} {res}"
        )
    except ImproperlyConfigured:
        pass

    uczelnia.pbn_app_name = "foo"
    uczelnia.save()

    uczelnia.pbn_app_token = None
    uczelnia.save()

    try:
        res = uczelnia.pbn_client()
        raise Exception(
            f"This should not happen {uczelnia.pbn_app_name} {uczelnia} {uczelnia.pbn_client} {res}"
        )
    except ImproperlyConfigured:
        pass

    uczelnia.pbn_app_token = "foo"
    uczelnia.save()

    assert uczelnia.pbn_client()
