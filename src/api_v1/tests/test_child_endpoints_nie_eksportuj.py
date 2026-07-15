"""Podrzędne (child) endpointy API muszą respektować flagę
``nie_eksportuj_przez_api`` rekordu nadrzędnego.

Główne viewsety publikacji filtrują ``.exclude(nie_eksportuj_przez_api=True)``,
ale endpointy podrzędne (streszczenia, autorstwa, identyfikatory zewnętrznych
baz) jechały na globalnym ``.objects.all()``. Pozwalało to anonimowemu
użytkownikowi enumerować PK child-rekordów i wyciągać dane rekordu chronionego
(treść streszczenia, obsadę autorską, identyfikatory zewnętrzne).
"""

import pytest
from django.urls import reverse

from bpp.models import Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych


def _assert_respektuje_flage(api_client, parent, child_pk, basename):
    """Sprawdza, że child jest widoczny gdy parent eksportowalny i znika
    (lista + detal 404) gdy parent ma ``nie_eksportuj_przez_api=True``."""
    list_url = reverse(f"api_v1:{basename}-list")
    detail_url = reverse(f"api_v1:{basename}-detail", args=(child_pk,))

    # Regresja: rekord nadrzędny eksportowalny -> child normalnie widoczny.
    parent.nie_eksportuj_przez_api = False
    parent.save()
    assert api_client.get(list_url).json()["count"] == 1
    assert api_client.get(detail_url).status_code == 200

    # Luka: rekord nadrzędny wyłączony z eksportu -> child niewidoczny.
    parent.nie_eksportuj_przez_api = True
    parent.save()
    assert api_client.get(list_url).json()["count"] == 0
    assert api_client.get(detail_url).status_code == 404


@pytest.mark.django_db
def test_child_streszczenie_zwarte(api_client, wydawnictwo_zwarte, jezyki):
    s = wydawnictwo_zwarte.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie=b"Tajne streszczenie"
    )
    _assert_respektuje_flage(
        api_client, wydawnictwo_zwarte, s.pk, "wydawnictwo_zwarte_streszczenie"
    )


@pytest.mark.django_db
def test_child_autor_zwarty(
    api_client, wydawnictwo_zwarte, autor_jan_kowalski, jednostka
):
    wa = wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    _assert_respektuje_flage(
        api_client, wydawnictwo_zwarte, wa.pk, "wydawnictwo_zwarte_autor"
    )


@pytest.mark.django_db
def test_child_streszczenie_ciagle(api_client, wydawnictwo_ciagle, jezyki):
    s = wydawnictwo_ciagle.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie=b"Tajne streszczenie"
    )
    _assert_respektuje_flage(
        api_client, wydawnictwo_ciagle, s.pk, "wydawnictwo_ciagle_streszczenie"
    )


@pytest.mark.django_db
def test_child_autor_ciagly(
    api_client, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
):
    wa = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    _assert_respektuje_flage(
        api_client, wydawnictwo_ciagle, wa.pk, "wydawnictwo_ciagle_autor"
    )


@pytest.mark.django_db
def test_child_zewnetrzna_baza_ciagle(api_client, wydawnictwo_ciagle, baza_wos):
    z = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych.objects.create(
        rekord=wydawnictwo_ciagle, baza=baza_wos
    )
    _assert_respektuje_flage(
        api_client,
        wydawnictwo_ciagle,
        z.pk,
        "wydawnictwo_ciagle_zewnetrzna_baza_danych",
    )


@pytest.mark.django_db
def test_child_autor_patent(api_client, patent, autor_jan_kowalski, jednostka):
    pa = patent.dodaj_autora(autor_jan_kowalski, jednostka)
    _assert_respektuje_flage(api_client, patent, pa.pk, "patent_autor")
