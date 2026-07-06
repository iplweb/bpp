import pytest
from django.db import IntegrityError

from bpp.models import RodzajJednostki


@pytest.mark.django_db
def test_rodzajjednostki_pola_i_defaulty():
    r = RodzajJednostki.objects.create(nazwa="Instytut")
    assert r.wyklucz_z_rankingu_autorow is False
    assert r.pokazuj_jako_odrebna_sekcje is False
    assert r.kolejnosc == 0
    assert str(r) == "Instytut"


@pytest.mark.django_db
def test_rodzajjednostki_nazwa_unique():
    RodzajJednostki.objects.create(nazwa="Katedra")
    with pytest.raises(IntegrityError):
        RodzajJednostki.objects.create(nazwa="Katedra")


@pytest.mark.django_db
def test_seed_rodzajow_obecny():
    kolo = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    assert kolo.wyklucz_z_rankingu_autorow is True
    assert kolo.pokazuj_jako_odrebna_sekcje is True
    assert RodzajJednostki.objects.get(nazwa="Standard")
    assert RodzajJednostki.objects.get(nazwa="Wydział")
