"""Filtr „Rodzaj dopasowania" na /rezultaty/ importu pracowników.

Testujemy KONTRAKT HTML/atrybutów, na którym operuje inline-JS filtra (samo
chowanie wierszy jest w JS — nie testujemy Playwrightem, YAGNI). Wiersze
tworzymy BEZPOŚREDNIO (``objects.create``, jawne ``zmiany_potrzebne``) — bez
pipeline'u ``analyze``, więc bez pułapki ``icontains``-ambient pod xdist.
"""

import re

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY


def _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA):
    """Import w fazie osób (Krok 2, edytowalny podgląd) z
    ``finished_successfully`` — inaczej pasek filtrów/tabela się nie
    wyrenderują (bramka ``{% if parent_object.finished_successfully %}``)."""
    imp = baker.make(ImportPracownikow, owner=admin_user, stan=stan)
    ImportPracownikow.objects.filter(pk=imp.pk).update(finished_successfully=True)
    imp.refresh_from_db()
    return imp


def _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=False, **kw):
    return ImportPracownikowRow.objects.create(
        parent=imp,
        confidence=confidence,
        autor=autor,
        utworz_nowego=utworz_nowego,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 7},
        **kw,
    )


def _results_url(imp):
    return reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )


def _get(admin_client, imp, **params):
    return admin_client.get(_results_url(imp), params).content.decode("utf-8")


def _opcja_selected(tresc, val):
    """Czy ``<option value="val" ... selected>`` (kolejność atrybutów swobodna
    — asercja luźna, nie kruchy dokładny string)."""
    return bool(
        re.search(rf'<option[^>]*value="{re.escape(val)}"[^>]*selected', tresc)
        or re.search(rf'<option[^>]*selected[^>]*value="{re.escape(val)}"', tresc)
    )


@pytest.mark.django_db
def test_wiersz_ma_data_confidence(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp, confidence=STATUS_BRAK)
    assert 'data-confidence="brak"' in _get(admin_client, imp)


@pytest.mark.django_db
def test_data_confidence_dla_twardego(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp, confidence=STATUS_TWARDY, autor=baker.make(Autor))
    assert 'data-confidence="twardy"' in _get(admin_client, imp)


@pytest.mark.django_db
def test_data_do_pominiecia_gdy_brak_decyzji(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=False)
    assert 'data-do-pominiecia="1"' in _get(admin_client, imp)


@pytest.mark.django_db
def test_brak_data_do_pominiecia_gdy_utworz_nowego(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=True)
    # Zawężone do RENDEROWANEGO atrybutu na <tr> — sam string „data-do-pominiecia"
    # występuje też w inline-JS (getAttribute), więc nie asertujemy go gołego.
    assert 'data-do-pominiecia="1"' not in _get(admin_client, imp)


@pytest.mark.django_db
def test_brak_data_do_pominiecia_gdy_autor_dopasowany(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp, confidence=STATUS_TWARDY, autor=baker.make(Autor))
    assert 'data-do-pominiecia="1"' not in _get(admin_client, imp)


@pytest.mark.django_db
def test_model_do_pominiecia_property(admin_user):
    imp = _imp(admin_user)
    r_brak = _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=False)
    r_decyzja = _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=True)
    r_autor = _row(imp, confidence=STATUS_TWARDY, autor=baker.make(Autor))
    assert r_brak.do_pominiecia is True
    assert r_decyzja.do_pominiecia is False
    assert r_autor.do_pominiecia is False


@pytest.mark.django_db
def test_select_rodzaj_ma_wszystkie_opcje(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp)
    tresc = _get(admin_client, imp)
    # Filtr rodzaju jest polem formularza GET (`?rodzaj=`), filtrującym
    # w SQL po CAŁYM imporcie — dawniej był to selektor sterujący JS-em.
    assert 'name="rodzaj"' in tresc
    for val in [
        "do-pominiecia",
        "twardy",
        "zgadywanie",
        "wielu",
        "brak",
        "reczny",
        "dedup",
    ]:
        assert f'value="{val}"' in tresc


@pytest.mark.django_db
def test_query_param_preselekcja(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp)
    tresc = _get(admin_client, imp, rodzaj="do-pominiecia")
    assert _opcja_selected(tresc, "do-pominiecia")


@pytest.mark.django_db
def test_query_param_smieciowy_ignorowany(admin_client, admin_user):
    imp = _imp(admin_user)
    _row(imp)
    tresc = _get(admin_client, imp, rodzaj="XXX")
    # Śmieciowy param → żadna „prawdziwa" opcja statusu nie jest zaznaczona
    # (fallback do „wszystkie").
    assert not _opcja_selected(tresc, "do-pominiecia")
    assert not _opcja_selected(tresc, "brak")


@pytest.mark.django_db
def test_ostrzezenie_ma_link_do_filtra(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    _row(imp, confidence=STATUS_BRAK, autor=None, utworz_nowego=False)
    url = reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "zostaną pominięte przy zapisie: 1" in tresc  # ostrzeżenie obecne
    assert f"{_results_url(imp)}?rodzaj=do-pominiecia" in tresc
