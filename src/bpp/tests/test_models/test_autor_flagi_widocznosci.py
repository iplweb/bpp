"""Flagi widoczności autora (następczynie dawnego ``Autor.pokazuj``).

Regresja: autor ukryty na stronach jednostek / w rankingu dostawał 404 na
swojej stronie, mimo że opis pracy linkował do niej (Rollbar #5235). Strona
autora zależy teraz wyłącznie od ``pokazuj_strone_autora``, a tę można
wyłączyć dopiero po wyłączeniu wyszukiwania i indeksu.
"""

import importlib
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.templatetags.prace import autor_nazwa
from bpp.views.autocomplete.search_services import globalne_wyszukiwanie_autora
from django_bpp.sitemaps import AutorSitemap
from ranking_autorow.views import RankingAutorowTable

SCHOWANA_STRONA = dict(
    pokazuj_strone_autora=False,
    pokazuj_w_wyszukiwaniu=False,
    pokazuj_w_indeksie=False,
)


def _schowany(**kw):
    return baker.make(
        Autor, nazwisko="Przykladowska", imiona="Zofia", **SCHOWANA_STRONA, **kw
    )


# --- walidacja ---------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "wyszukiwanie,indeks", [(True, True), (True, False), (False, True)]
)
def test_clean_schowana_strona_wymaga_wylaczenia_wyszukiwania_i_indeksu(
    wyszukiwanie, indeks
):
    autor = Autor(
        nazwisko="Przykladowska",
        imiona="Zofia",
        pokazuj_strone_autora=False,
        pokazuj_w_wyszukiwaniu=wyszukiwanie,
        pokazuj_w_indeksie=indeks,
    )
    with pytest.raises(ValidationError) as exc:
        autor.clean()
    assert "pokazuj_strone_autora" in exc.value.message_dict


def test_clean_schowana_strona_po_wylaczeniu_wyszukiwania_i_indeksu():
    Autor(nazwisko="Przykladowska", imiona="Zofia", **SCHOWANA_STRONA).clean()


@pytest.mark.django_db(transaction=True)
def test_constraint_blokuje_masowe_obejscie_walidacji():
    autor = baker.make(Autor)
    with pytest.raises(IntegrityError), transaction.atomic():
        Autor.objects.filter(pk=autor.pk).update(pokazuj_strone_autora=False)


# --- strona autora -----------------------------------------------------------


@pytest.mark.django_db
def test_strona_autora_dziala_mimo_ukrycia_w_jednostce_rankingu_indeksie_api(
    client,
):
    """Regresja Rollbar #5235: dawne ``pokazuj=False`` nie daje już 404."""
    autor = baker.make(
        Autor,
        pokazuj_na_stronie_jednostki=False,
        pokazuj_w_rankingu=False,
        pokazuj_w_indeksie=False,
        pokazuj_w_api=False,
    )
    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_schowana_strona_autora_404_dla_anonima(client):
    autor = _schowany()
    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_schowana_strona_autora_widoczna_dla_redakcji(client, django_user_model):
    autor = _schowany()
    user = django_user_model.objects.create_user("redaktor", password="x")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    client.force_login(user)
    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 200


# --- linki do strony autora --------------------------------------------------


@pytest.mark.django_db
def test_opis_pracy_nie_linkuje_schowanej_strony():
    autor = _schowany()
    wpis = SimpleNamespace(
        zapisany_jako="Przykladowska Zofia", czy_nasz=False, autor=autor
    )
    html = str(autor_nazwa(wpis, links="normal"))
    assert "<a " not in html
    assert "PRZYKLADOWSKA ZOFIA" in html


@pytest.mark.django_db
def test_opis_pracy_linkuje_autora_ukrytego_tylko_w_jednostce():
    autor = baker.make(
        Autor, pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
    )
    wpis = SimpleNamespace(zapisany_jako="Ktos", czy_nasz=False, autor=autor)
    html = str(autor_nazwa(wpis, links="normal"))
    assert reverse("bpp:browse_autor", args=(autor.slug,)) in html


@pytest.mark.django_db
def test_ranking_nie_linkuje_schowanej_strony():
    autor = _schowany()
    html = str(RankingAutorowTable([]).render_autor(SimpleNamespace(autor=autor)))
    assert "<a " not in html
    assert "Przykladowska" in html


# --- indeks, wyszukiwanie, sitemap --------------------------------------------


@pytest.mark.django_db
def test_indeks_autorow_pomija_ukrytych_w_indeksie(client):
    baker.make(Autor, nazwisko="Widocznawska", imiona="Zofia")
    baker.make(
        Autor, nazwisko="Niewidocznawska", imiona="Zofia", pokazuj_w_indeksie=False
    )
    tresc = client.get(reverse("bpp:browse_autorzy")).content.decode()
    assert "Widocznawska" in tresc
    assert "Niewidocznawska" not in tresc


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tylko_wyszukiwalni,znaleziony", [(True, False), (False, True)]
)
def test_wyszukiwanie_globalne_respektuje_flage(tylko_wyszukiwalni, znaleziony):
    autor = baker.make(
        Autor, nazwisko="Przykladowska", imiona="Zofia", pokazuj_w_wyszukiwaniu=False
    )
    querysets = []
    globalne_wyszukiwanie_autora(
        querysets, "Przykladowska", tylko_wyszukiwalni=tylko_wyszukiwalni
    )
    znalezieni = {a.pk for qs in querysets for a in qs}
    assert (autor.pk in znalezieni) is znaleziony


@pytest.mark.django_db
def test_sitemap_pomija_schowane_strony():
    widoczny = baker.make(Autor, nazwisko="Widocznawska", imiona="Zofia")
    schowany = _schowany()
    pks = {a.pk for a in AutorSitemap().items()}
    assert widoczny.pk in pks
    assert schowany.pk not in pks


# --- migracja danych ---------------------------------------------------------


def test_migracja_przepisuje_pokazuj_do_czterech_flag():
    mig = importlib.import_module("bpp.migrations.0500_autor_flagi_widocznosci")
    Model = mock.MagicMock()
    apps = mock.MagicMock()
    apps.get_model.return_value = Model

    mig.przepisz_pokazuj(apps, None)

    Model.objects.filter.assert_called_once_with(pokazuj=False)
    Model.objects.filter.return_value.update.assert_called_once_with(
        pokazuj_na_stronie_jednostki=False,
        pokazuj_w_rankingu=False,
        pokazuj_w_indeksie=False,
        pokazuj_w_api=False,
    )
