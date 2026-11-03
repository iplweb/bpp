"""Testy integracyjne podstrony autora: układ 2-kolumnowy + linki do raportu."""

import re

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
def test_pusty_biogram_nie_renderuje_naglowka(client):
    autor = baker.make(Autor, biogram="", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "autor-page__biogram-tresc" not in tresc


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


def _szerokosc_celi(tresc, klucz):
    """Klasa szerokości (``large-6`` / ``large-12``) komórki pasu z sekcją."""
    m = re.search(
        r'<div class="cell (large-\d+) autor-page__pas-cela[^"]*"'
        rf'\s+data-sekcja="{re.escape(klucz)}">',
        tresc,
    )
    assert m, f"brak sekcji {klucz} na stronie"
    return m.group(1)


@pytest.mark.django_db
def test_wizytowka_i_afiliacja_w_jednej_parze(client):
    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert _szerokosc_celi(tresc, "wizytowka") == "large-6"
    assert _szerokosc_celi(tresc, "afiliacja") == "large-6"
    # w tym samym pasie: między nimi nie zaczyna się nowy pas
    miedzy = tresc[
        tresc.index('data-sekcja="wizytowka"') : tresc.index('data-sekcja="afiliacja"')
    ]
    assert 'autor-page__pas"' not in miedzy


@pytest.mark.django_db
def test_pusta_wizytowka_znika_a_afiliacja_zajmuje_caly_pas(client):
    # bez zdjęcia i biogramu wizytówka jest pusta — nie może zostawić
    # pustej połówki obok afiliacji.
    autor = baker.make(Autor, biogram="")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert 'data-sekcja="wizytowka"' not in tresc
    assert _szerokosc_celi(tresc, "afiliacja") == "large-12"


@pytest.mark.django_db
def test_wyszukiwarka_na_cala_szerokosc_bez_karty(client):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert _szerokosc_celi(tresc, "wyszukiwarka") == "large-12"
    poz = tresc.index('data-sekcja="wyszukiwarka"')
    assert not tresc[poz:].lstrip('">\n ').startswith('<div class="autor-page__karta"')


@pytest.mark.django_db
def test_afiliacja_jest_w_karcie(client):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    poz = tresc.index('data-sekcja="afiliacja"')
    assert tresc.index('class="autor-page__karta"', poz) < tresc.index(
        "Identyfikatory", poz
    )


@pytest.mark.django_db
def test_szerokosc_z_konfiguracji_uczelni(client, uczelnia):
    from bpp.profil_autora import KLUCZ_WIZYTOWKA, SZEROKOSC_CALA

    uczelnia.uklad_profilu_autora = [
        {"klucz": KLUCZ_WIZYTOWKA, "szerokosc": SZEROKOSC_CALA, "widoczna": True}
    ]
    uczelnia.save()

    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert _szerokosc_celi(tresc, "wizytowka") == "large-12"
    # afiliacja straciła parę → też sama na cały pas
    assert _szerokosc_celi(tresc, "afiliacja") == "large-12"


@pytest.mark.django_db
def test_komorka_pary_oznaczona_jako_polowka(client):
    # Klasa --polowka pozwala sekcjom (np. wykresom) ułożyć się w kolumnę.
    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert re.search(
        r'autor-page__pas-cela autor-page__pas-cela--polowka"\s+'
        r'data-sekcja="afiliacja"',
        tresc,
    )
