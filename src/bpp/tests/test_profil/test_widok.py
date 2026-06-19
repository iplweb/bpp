"""Testy integracyjne podstrony autora: układ 2-kolumnowy + linki do raportu."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor


@pytest.mark.django_db
def test_strona_renderuje_biogram_i_wyszukiwarke(client):
    autor = baker.make(Autor, biogram="**Bio** autora", biogram_format="md")
    resp = client.get(autor.get_absolute_url())
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "<strong>Bio</strong>" in tresc
    assert "Wyszukaj publikacje autora" in tresc


@pytest.mark.django_db
def test_biogram_jest_staly_w_lewej_kolumnie(client):
    # Biogram nie jest już sekcją konfigurowalną — jest stały w lewej kolumnie,
    # renderowany wprost z autor.biogram_html (gdy niepusty).
    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "Tekst biogramu" in tresc
    assert "autor-page__biogram-tresc" in tresc


@pytest.mark.django_db
def test_pusty_biogram_nie_renderuje_naglowka(client):
    autor = baker.make(Autor, biogram="", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "autor-page__biogram-tresc" not in tresc


@pytest.mark.django_db
def test_uklad_2_kolumnowy_obecny(client):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "autor-page__kolumna-lewa" in tresc
    assert "autor-page__kolumna-prawa" in tresc


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
