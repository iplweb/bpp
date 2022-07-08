import pytest
from model_bakery import baker

from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_liczba_arkuszy_wydawniczych(wydawnictwo_zwarte_z_autorem):
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 41000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "1.02"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 39000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "0.97"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 60000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "1.50"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 20000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "0.50"


@pytest.mark.django_db
def test_generowanie_opisu_bibliograficznego_informacje_wydawnictwo_nadrzedne(denorms):
    wz1 = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Pięćset")
    wz2 = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Plus")

    wz1.informacje = "To sie ma pojawic"
    wz1.wydawnictwo_nadrzedne = wz2
    wz1.save()
    denorms.flush()
    assert "To sie ma pojawic" in wz1.opis_bibliograficzny_cache

    wz1.informacje = ""
    wz1.wydawnictwo_nadrzedne = wz2
    wz1.save()
    denorms.flush()
    assert "Pięćset" in wz1.opis_bibliograficzny_cache
    assert "W: Plus" in wz1.opis_bibliograficzny_cache

    wz1.informacje = ""
    wz1.wydawnictwo_nadrzedne = None
    wz1.save()
    denorms.flush()
    assert "Pięćset" in wz1.opis_bibliograficzny_cache
    assert "Plus" not in wz1.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_wydawnictwo_property(wydawnictwo_zwarte, wydawca):
    wydawnictwo_zwarte.wydawca = None
    wydawnictwo_zwarte.wydawca_opis = "123"
    assert wydawnictwo_zwarte.wydawnictwo == "123"

    wydawnictwo_zwarte.wydawca = wydawca
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy 123"

    wydawnictwo_zwarte.wydawca_opis = ". Lol"
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy. Lol"

    wydawnictwo_zwarte.wydawca_opis = None
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy"
