"""FD#451: importer dopasowywał czasopismo po tytule, a nie po ISSN.

Artykuł z „Applied Sciences" (ISSN 2076-3417, na liście ministerialnej jako
„Applied Sciences-Basel") trafiał do innego rekordu źródła o nazwie
„Applied Sciences" (trygramowe dopasowanie tytułu), przez co w kolejnym
kroku importer proponował złą punktację (40 zamiast 100 pkt).
"""

import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from crossref_bpp.admin.helpers import convert_crossref_to_changeform_initial_data
from crossref_bpp.core import Komparator, StatusPorownania
from import_common.core import matchuj_zrodlo
from importer_publikacji.views.steps import _source_initial_auto_match


class _Sesja:
    def __init__(self, normalized_data):
        self.normalized_data = normalized_data


@pytest.fixture
def zrodla_applied_sciences():
    zle = baker.make(Zrodlo, nazwa="Applied Sciences", issn="", e_issn="")
    dobre = baker.make(
        Zrodlo,
        nazwa="Applied Sciences-Basel",
        issn="2076-3417",
        e_issn="2076-3417",
    )
    return zle, dobre


@pytest.mark.django_db
def test_fd451_importer_wybiera_zrodlo_po_issn_a_nie_po_tytule(
    zrodla_applied_sciences,
):
    _zle, dobre = zrodla_applied_sciences
    initial = _source_initial_auto_match(
        _Sesja({"source_title": "Applied Sciences", "e_issn": "2076-3417"})
    )
    assert initial["zrodlo"] == dobre.pk


@pytest.mark.django_db
def test_fd451_issn_w_innym_polu_i_bez_myslnika():
    """e-ISSN z importu trafia w pole ``issn`` źródła, zapis bez myślnika."""
    baker.make(Zrodlo, nazwa="Applied Sciences", issn="", e_issn="")
    dobre = baker.make(
        Zrodlo, nazwa="Applied Sciences-Basel", issn="2076-3417", e_issn=""
    )
    initial = _source_initial_auto_match(
        _Sesja({"source_title": "Applied Sciences", "e_issn": "20763417"})
    )
    assert initial["zrodlo"] == dobre.pk


@pytest.mark.django_db
def test_fd451_bez_pasujacego_issn_fallback_na_tytul(zrodla_applied_sciences):
    zle, _dobre = zrodla_applied_sciences
    wynik = Komparator.porownaj_zrodlo("Applied Sciences", issn="9999-9999")
    assert wynik.status == StatusPorownania.LUZNE
    assert wynik.rekord_po_stronie_bpp == zle


@pytest.mark.django_db
def test_fd451_issn_bez_tytulu(zrodla_applied_sciences):
    _zle, dobre = zrodla_applied_sciences
    wynik = Komparator.porownaj_zrodlo(None, e_issn="2076-3417")
    assert wynik.status == StatusPorownania.DOKLADNE
    assert wynik.rekord_po_stronie_bpp == dobre


@pytest.mark.django_db
def test_fd451_niejednoznaczny_issn_fallback_na_tytul():
    """Dwa źródła z tym samym ISSN — nie zgadujemy, decyduje tytuł."""
    baker.make(Zrodlo, nazwa="Czasopismo A", issn="1234-5678")
    b = baker.make(Zrodlo, nazwa="Czasopismo B", issn="1234-5678")
    wynik = Komparator.porownaj_zrodlo("Czasopismo B", issn="1234-5678")
    assert wynik.rekord_po_stronie_bpp == b


@pytest.mark.django_db
def test_fd451_crossref_admin_prefill_po_issn(zrodla_applied_sciences):
    _zle, dobre = zrodla_applied_sciences
    data = convert_crossref_to_changeform_initial_data(
        {
            "container-title": ["Applied Sciences"],
            "issn-type": [{"type": "electronic", "value": "2076-3417"}],
            "ISSN": ["2076-3417"],
        }
    )
    assert data["zrodlo"] == dobre.pk


@pytest.mark.django_db
def test_fd451_matchuj_zrodlo_eissn_w_polu_issn():
    """Wspólny ``matchuj_zrodlo``: e-ISSN z danych pasuje do pola ``issn``."""
    baker.make(Zrodlo, nazwa="Applied Sciences", issn="", e_issn="")
    dobre = baker.make(
        Zrodlo, nazwa="Applied Sciences-Basel", issn="2076-3417", e_issn=""
    )
    assert matchuj_zrodlo("Applied Sciences", e_issn="2076-3417") == dobre
