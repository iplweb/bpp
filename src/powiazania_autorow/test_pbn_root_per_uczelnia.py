import pytest

from powiazania_autorow.queries import _pbn_root


@pytest.mark.django_db
def test_pbn_root_uzywa_uczelni_z_argumentu(uczelnia1, uczelnia2):
    uczelnia1.pbn_api_root = "https://pbn-U1.example/api"
    uczelnia1.save()
    uczelnia2.pbn_api_root = "https://pbn-U2.example/api"
    uczelnia2.save()

    assert _pbn_root(uczelnia1) == "https://pbn-U1.example/api"
    assert _pbn_root(uczelnia2) == "https://pbn-U2.example/api"


@pytest.mark.django_db
def test_pbn_root_none_uczelnia_zwraca_none():
    assert _pbn_root(None) is None
