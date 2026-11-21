"""Warunek „DOI równe (puste)” ma znajdować rekordy z NULL w polu DOI."""

import pytest
from multiseek.logic import DIFFERENT_NONE, EQUAL_NONE

from bpp.models.cache import Rekord
from bpp.multiseek_registry import DOIQueryObject, registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


@pytest.fixture
def prace_z_doi_i_bez(wydawnictwo_ciagle, wydawnictwo_zwarte):
    wydawnictwo_ciagle.doi = None
    wydawnictwo_ciagle.save()
    wydawnictwo_zwarte.doi = "10.1234/demo"
    wydawnictwo_zwarte.save()
    return wydawnictwo_ciagle, wydawnictwo_zwarte


def _tytuly(q):
    return set(Rekord.objects.filter(q).values_list("tytul_oryginalny", flat=True))


@pytest.mark.django_db
def test_doi_rowne_puste_znajduje_null(prace_z_doi_i_bez):
    bez_doi, z_doi = prace_z_doi_i_bez
    q = DOIQueryObject().real_query("", str(EQUAL_NONE))
    assert _tytuly(q) == {bez_doi.tytul_oryginalny}


@pytest.mark.django_db
def test_doi_rozne_puste_pomija_null(prace_z_doi_i_bez):
    bez_doi, z_doi = prace_z_doi_i_bez
    q = DOIQueryObject().real_query("", str(DIFFERENT_NONE))
    assert _tytuly(q) == {z_doi.tytul_oryginalny}


@pytest.mark.django_db
def test_doi_rowne_wartosc_bez_zmian(prace_z_doi_i_bez):
    bez_doi, z_doi = prace_z_doi_i_bez
    q = DOIQueryObject().real_query("10.1234/demo", str(EQUAL_NONE))
    assert _tytuly(q) == {z_doi.tytul_oryginalny}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,oczekiwany",
    [
        (EQUAL_NONE, '(doi = None or doi = "")'),
        (DIFFERENT_NONE, '(doi != None and doi != "")'),
    ],
)
def test_doi_puste_do_djangoql(operator, oczekiwany):
    frag = leaf_to_djangoql(
        registry, {"field": "DOI", "operator": str(operator), "value": ""}
    )
    assert frag == oczekiwany


@pytest.mark.django_db
def test_doi_puste_djangoql_daje_ten_sam_wynik(prace_z_doi_i_bez):
    from djangoql.queryset import apply_search

    from bpp.djangoql_schema import BppQLSchemaOgraniczony

    bez_doi, _ = prace_z_doi_i_bez
    frag = leaf_to_djangoql(
        registry, {"field": "DOI", "operator": str(EQUAL_NONE), "value": ""}
    )
    wynik = apply_search(Rekord.objects.all(), frag, schema=BppQLSchemaOgraniczony)
    assert set(wynik.values_list("tytul_oryginalny", flat=True)) == {
        bez_doi.tytul_oryginalny
    }


def test_formularz_wyszukiwania_ma_polskie_kolumny():
    from multiseek.models import SearchForm

    import bpp.admin  # noqa: F401  — ustawia etykiety pól

    assert SearchForm._meta.get_field("owner").verbose_name == "właściciel"
    assert SearchForm._meta.get_field("public").verbose_name == "publiczny"
