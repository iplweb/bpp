"""Testy integracyjne podstrony autora: render sekcji + linki do raportu."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from bpp.profil_autora import KLUCZ_BIOGRAM, KLUCZ_WYSZUKIWARKA


@pytest.mark.django_db
def test_strona_renderuje_biogram_i_wyszukiwarke(client):
    autor = baker.make(Autor, biogram="**Bio** autora", biogram_format="md")
    resp = client.get(autor.get_absolute_url())
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "<strong>Bio</strong>" in tresc
    assert "Wyszukaj publikacje autora" in tresc


@pytest.mark.django_db
def test_uklad_pozwala_ukryc_biogram(client):
    autor = baker.make(
        Autor,
        biogram="**Bio** autora",
        biogram_format="md",
        uklad_profilu=[
            {"klucz": KLUCZ_BIOGRAM, "widoczna": False, "limit": None},
            {"klucz": KLUCZ_WYSZUKIWARKA, "widoczna": True, "limit": None},
        ],
    )
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "<strong>Bio</strong>" not in tresc
    # wyszukiwarka (obowiązkowa) nadal jest
    assert "Wyszukaj publikacje autora" in tresc


@pytest.mark.django_db
def test_brak_linkow_raportu_gdy_raport_nieaktywny(client):
    from nowe_raporty.models import DefinicjaRaportu

    DefinicjaRaportu.objects.filter(slug="raport-autorow").update(aktywny=False)
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "Raport autora" not in tresc


@pytest.mark.django_db
def test_linki_raportu_dla_publicznego_raportu(client):
    from nowe_raporty.models import DefinicjaRaportu

    DefinicjaRaportu.objects.filter(slug="raport-autorow").delete()
    baker.make(
        DefinicjaRaportu,
        slug="raport-autorow",
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
    )
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "Raport autora" in tresc
    assert reverse("nowe_raporty:raport_form", args=["raport-autorow"]) in tresc
