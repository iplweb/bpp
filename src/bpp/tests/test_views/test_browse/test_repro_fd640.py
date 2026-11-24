"""FD#640 — pełna strona autora tylko dla autorów uczelni.

Autor spoza uczelni (wszystkie przypisania wyłącznie do jednostki obcej
uczelni) dostaje pod swoim dotychczasowym adresem prostą stronę
informacyjną zamiast profilu. Autorzy uczelni — obecni i byli — bez zmian.
"""

from datetime import date

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka

PROFIL = 'class="autor-page__pasy"'
STRONA_OBCEGO = "Autor spoza uczelni."


@pytest.fixture
def uczelnia_z_obca(uczelnia_z_obca_jednostka):
    return uczelnia_z_obca_jednostka


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
            reverse("api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk})
        )
        assert res.status_code == 200
        return res.json()["profil_url"]

    assert profil_url(autor_obcy) is None
    assert profil_url(nasz) is not None


@pytest.mark.django_db
def test_fd640_jednostka_bledna_o_ujemnym_pk_to_nie_uczelnia(
    client, uczelnia_z_obca, wydzial
):
    """Jednostka „Błędna” (pk < 0) ze starych wdrożeń jest sztuczna."""
    bledna = baker.make(Jednostka, pk=-1, uczelnia=uczelnia_z_obca, parent=wydzial)
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=bledna)
    assert autor.jest_spoza_uczelni(uczelnia_z_obca)
    assert STRONA_OBCEGO in _strona(client, autor)


@pytest.mark.django_db
def test_fd640_aktualna_jednostka_w_uczelni_wystarcza(uczelnia_z_obca, jednostka):
    """Sama aktualna jednostka (bez wiersza przypisania) też czyni autorem
    uczelni — sprawdzamy obie drogi."""
    autor = baker.make(Autor)
    Autor.objects.filter(pk=autor.pk).update(aktualna_jednostka=jednostka)
    assert not autor.jest_spoza_uczelni(uczelnia_z_obca)
    assert autor in Autor.objects.autorzy_uczelni(uczelnia_z_obca)


@pytest.fixture
def druga_uczelnia(db):
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    site = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    return baker.make(Uczelnia, skrot="UB", nazwa="Uczelnia B", site=site)


@pytest.mark.django_db
def test_fd640_dwie_uczelnie_granica_per_host(
    client, settings, uczelnia_z_obca, jednostka, druga_uczelnia
):
    """Pracownik uczelni A: na hoście A pełny profil, na hoście B prosta
    strona (dla B jest autorem spoza uczelni)."""
    settings.ALLOWED_HOSTS = ["*"]
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    url = reverse("bpp:browse_autor", args=(autor.slug,))

    tresc_a = client.get(url, HTTP_HOST="testserver").content.decode("utf-8")
    assert PROFIL in tresc_a

    tresc_b = client.get(url, HTTP_HOST="uczelnia-b.example.com").content.decode(
        "utf-8"
    )
    assert STRONA_OBCEGO in tresc_b
    assert PROFIL not in tresc_b


@pytest.mark.django_db
def test_fd640_sitemap_dwie_uczelnie(
    uczelnia_z_obca, autor_obcy, jednostka, druga_uczelnia
):
    """Mapa jest wspólna: zostaje autor, który jest autorem KTÓREJKOLWIEK
    uczelni; znika tylko obcy dla wszystkich."""
    from django_bpp.sitemaps import AutorSitemap

    nasz = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)

    items = AutorSitemap().items()
    assert nasz in items
    assert autor_obcy not in items


def test_fd640_zmiana_przypisan_uniewaznia_cache_publiczny():
    """Przypisania decydują o rodzaju strony autora — ich zapis (także
    z importów, bez zapisu ``Autor``) musi unieważniać cache stron."""
    from bpp.apps import BppConfig

    assert "Autor_Jednostka" in BppConfig.MODELE_INWALIDUJACE_CACHE_PUBLICZNY
