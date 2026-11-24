"""FD#640 — pełna strona autora tylko dla autorów uczelni.

Autor spoza uczelni (wszystkie przypisania wyłącznie do jednostki obcej
uczelni) dostaje pod swoim dotychczasowym adresem prostą stronę
informacyjną zamiast profilu. Autorzy uczelni — obecni i byli — bez zmian.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka

PROFIL = 'class="autor-page__pasy"'
STRONA_OBCEGO = "Autor spoza uczelni."


@pytest.fixture
def uczelnia_z_obca(uczelnia, obca_jednostka):
    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()
    return uczelnia


@pytest.fixture
def autor_obcy(uczelnia_z_obca, obca_jednostka):
    autor = baker.make(Autor, nazwisko="Obcy", imiona="Jan")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    return autor


def _strona(client, autor):
    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 200
    return res.content.decode("utf-8")


@pytest.mark.django_db
def test_fd640_autor_obcy_dostaje_prosta_strone(client, autor_obcy):
    tresc = _strona(client, autor_obcy)
    assert STRONA_OBCEGO in tresc
    assert PROFIL not in tresc
    assert "Pokaż prace współautorskie" in tresc
    assert '<meta name="robots" content="noindex"/>' in tresc


@pytest.mark.django_db
def test_fd640_stary_url_po_pk_tez_daje_prosta_strone(client, autor_obcy):
    res = client.get(reverse("bpp:browse_autor", args=(autor_obcy.pk,)))
    assert res.status_code == 200
    assert STRONA_OBCEGO in res.content.decode("utf-8")


@pytest.mark.django_db
def test_fd640_obecny_pracownik_ma_pelny_profil(client, uczelnia_z_obca, jednostka):
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    tresc = _strona(client, autor)
    assert PROFIL in tresc
    assert STRONA_OBCEGO not in tresc


@pytest.mark.django_db
def test_fd640_byly_pracownik_ma_pelny_profil(
    client, uczelnia_z_obca, jednostka, obca_jednostka
):
    """Zakończone zatrudnienie w jednostce uczelni + bieżąca jednostka obca
    — nadal autor uczelni."""
    from datetime import date

    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2000, 1, 1),
        zakonczyl_prace=date(2010, 1, 1),
    )
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    tresc = _strona(client, autor)
    assert PROFIL in tresc
    assert STRONA_OBCEGO not in tresc


@pytest.mark.django_db
def test_fd640_jednostka_nieskupiajaca_pracownikow_to_nadal_uczelnia(
    client, uczelnia_z_obca, wydzial
):
    """Doktoranci/studenci/emeryci: jednostka bez „skupia pracowników”, ale
    nie obca — autor jest autorem uczelni."""
    doktoranci = baker.make(
        Jednostka, uczelnia=uczelnia_z_obca, parent=wydzial, skupia_pracownikow=False
    )
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=doktoranci)
    assert PROFIL in _strona(client, autor)


@pytest.mark.django_db
def test_fd640_autor_bez_przypisan_bez_zmian(client, uczelnia_z_obca):
    """Brak jakiegokolwiek przypisania to nie dowód obcości — profil jak dawniej."""
    autor = baker.make(Autor)
    assert PROFIL in _strona(client, autor)


@pytest.mark.django_db
def test_fd640_bez_uczelni_nikt_nie_jest_obcy(autor_obcy):
    """Bez ustalonej uczelni (pusta baza) strona autora działa jak dawniej."""
    assert not autor_obcy.jest_spoza_uczelni(None)


@pytest.mark.django_db
def test_fd640_queryset_spoza_uczelni(uczelnia_z_obca, autor_obcy, jednostka):
    nasz = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)
    bez_przypisan = baker.make(Autor)

    spoza = set(Autor.objects.spoza_uczelni(uczelnia_z_obca))
    assert autor_obcy in spoza
    assert nasz not in spoza
    assert bez_przypisan not in spoza
    assert set(Autor.objects.autorzy_uczelni(uczelnia_z_obca)) == {nasz}
    assert Autor.objects.spoza_uczelni(None).count() == 0


@pytest.mark.django_db
def test_fd640_redaktor_widzi_prosta_strone_z_linkiem_do_edycji(
    admin_client, autor_obcy
):
    tresc = _strona(admin_client, autor_obcy)
    assert STRONA_OBCEGO in tresc
    assert PROFIL not in tresc
    assert reverse("admin:bpp_autor_change", args=(autor_obcy.pk,)) in tresc


@pytest.mark.django_db
def test_fd640_sitemap_pomija_autora_obcego(autor_obcy, jednostka):
    from django_bpp.sitemaps import AutorSitemap

    nasz = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)

    items = AutorSitemap().items()
    assert nasz in items
    assert autor_obcy not in items


@pytest.mark.django_db
def test_fd640_api_recent_publications_bez_profil_url_dla_obcego(
    client, autor_obcy, jednostka
):
    nasz = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)

    def profil_url(autor):
        res = client.get(
            reverse(
                "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
            )
        )
        assert res.status_code == 200
        return res.json()["profil_url"]

    assert profil_url(autor_obcy) is None
    assert profil_url(nasz) is not None
