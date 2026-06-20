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


def _wytnij_kolumne(tresc, klasa):
    """Zwróć fragment HTML danej kolumny (od jej diva do końca treści).

    Wystarczy do testu „w której kolumnie" — porównujemy pozycje markerów.
    """
    return tresc[tresc.index(klasa) :]


@pytest.mark.django_db
def test_domyslnie_biogram_i_identyfikatory_w_lewej_kolumnie(client):
    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    poz_lewa = tresc.index("autor-page__kolumna-lewa")
    poz_prawa = tresc.index("autor-page__kolumna-prawa")
    # biogram i identyfikatory renderują się PRZED początkiem prawej kolumny
    assert poz_lewa < tresc.index("autor-page__biogram-tresc") < poz_prawa
    assert poz_lewa < tresc.index("Identyfikatory") < poz_prawa
    # wyszukiwarka też w lewej (domyślnie)
    assert poz_lewa < tresc.index("Wyszukaj publikacje autora") < poz_prawa


@pytest.mark.django_db
def test_szerokosc_kolumn_domyslnie_6_6(client):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "cell large-6 autor-page__kolumna-lewa" in tresc
    assert "cell large-6 autor-page__kolumna-prawa" in tresc


@pytest.mark.django_db
def test_przeniesienie_biogramu_do_prawej_kolumny(client, uczelnia):
    from bpp.profil_autora import KLUCZ_BIOGRAM, KOLUMNA_PRAWA

    uczelnia.uklad_profilu_autora = [
        {"klucz": KLUCZ_BIOGRAM, "kolumna": KOLUMNA_PRAWA, "widoczna": True}
    ]
    uczelnia.save()

    autor = baker.make(Autor, biogram="Tekst biogramu", biogram_format="md")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    # biogram musi renderować się ZA początkiem prawej kolumny
    assert tresc.index("autor-page__biogram-tresc") > tresc.index(
        "autor-page__kolumna-prawa"
    )


@pytest.mark.django_db
def test_konfigurowalna_szerokosc_lewej_kolumny(client, uczelnia):
    uczelnia.szerokosc_lewej_kolumny = 8
    uczelnia.save()

    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "cell large-8 autor-page__kolumna-lewa" in tresc
    assert "cell large-4 autor-page__kolumna-prawa" in tresc


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
