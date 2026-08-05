"""``dopasuj_profil`` / ``wybierz_profil_fallback`` respektują uczelnię."""

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.mapping import dopasuj_profil, wybierz_profil_fallback
from import_pracownikow.models import ProfilMapowania

MAPOWANIE = {"nazwisko": "nazwisko", "imię": "imię", "jednostka": "nazwa_jednostki"}
NAGLOWKI = ["nazwisko", "imię", "jednostka"]


@pytest.mark.django_db
def test_dopasuj_profil_tylko_biezaca_uczelnia():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a, mapowanie=MAPOWANIE)
    baker.make(ProfilMapowania, nazwa="B", uczelnia=b, mapowanie=MAPOWANIE)
    assert dopasuj_profil(NAGLOWKI, a) == p_a
    assert dopasuj_profil(NAGLOWKI, b) != p_a


@pytest.mark.django_db
def test_fallback_ostatnio_uzyty_per_uczelnia():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    baker.make(
        ProfilMapowania,
        nazwa="B",
        uczelnia=b,
        mapowanie=MAPOWANIE,
        ostatnio_uzyty=timezone.now(),
    )
    # Najnowszy globalnie jest B, ale dla A nie wolno go podnieść:
    assert wybierz_profil_fallback(NAGLOWKI, a) is None
