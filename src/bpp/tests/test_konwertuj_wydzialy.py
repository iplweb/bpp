import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki, Wydzial


@pytest.mark.django_db
def test_kazdy_wydzial_daje_ukryty_wezel():
    w = baker.make(Wydzial, nazwa="Wydz Lekarski", skrot="WL", kolejnosc=3)
    call_command("konwertuj_wydzialy_na_jednostki")
    j = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert j.widoczna is False
    assert j.aktualna is False
    assert j.rodzaj == RodzajJednostki.objects.get(nazwa="Wydział")
    assert j.nazwa == "Wydz Lekarski"
    assert j.parent_id is None


@pytest.mark.django_db
def test_idempotentna():
    w = baker.make(Wydzial, nazwa="Wydz X", skrot="WX")
    call_command("konwertuj_wydzialy_na_jednostki")
    call_command("konwertuj_wydzialy_na_jednostki")
    assert Jednostka.objects.filter(legacy_wydzial_id=w.id).count() == 1


@pytest.mark.django_db
def test_kolejnosc_ujemna_clampowana():
    w = baker.make(Wydzial, nazwa="Wydz Neg", skrot="WN", kolejnosc=-5)
    call_command("konwertuj_wydzialy_na_jednostki")
    j = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert j.kolejnosc == 0
