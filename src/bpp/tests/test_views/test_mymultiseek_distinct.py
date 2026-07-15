"""Testy decyzji o ``distinct()`` w multiseeku (#10 security review).

Sprawdzają, że o zwielokrotnieniu rekordów decyduje strukturalne wykrycie
złączeń (``query.alias_map`` → realne nazwy tabel), a nie substring w tekście
SQL (kruche: zależne od aliasów i formatowania).
"""

import pytest

from bpp.models.cache import Rekord
from bpp.views.mymultiseek import (
    MULTISEEK_MNOZACE_ZLACZENIA,
    MyMultiseekResults,
)


class _FakeJoin:
    def __init__(self, table_name):
        self.table_name = table_name


class _FakeQuery:
    def __init__(self, aliasy):
        # klucz = alias (może być T2/T3 przy self-joinie), wartość ma table_name
        self.alias_map = {alias: _FakeJoin(t) for alias, t in aliasy.items()}


class _FakeQS:
    def __init__(self, aliasy):
        self.query = _FakeQuery(aliasy)


def test_wykrywa_zlaczenie_mnozace_po_nazwie_tabeli():
    qs = _FakeQS({"bpp_rekord": "bpp_rekord", "bpp_autorzy_mat": "bpp_autorzy_mat"})
    assert MyMultiseekResults._zapytanie_mnozy_wiersze(qs) is True


def test_wykrywa_po_table_name_nawet_gdy_alias_jest_inny():
    # Alias 'T3' (np. self-join), ale realna tabela to złączenie mnożące.
    qs = _FakeQS({"bpp_rekord": "bpp_rekord", "T3": "bpp_zewnetrzne_bazy_view"})
    assert MyMultiseekResults._zapytanie_mnozy_wiersze(qs) is True


def test_bez_zlaczen_mnozacych_zwraca_false():
    qs = _FakeQS({"bpp_rekord": "bpp_rekord", "bpp_zrodlo": "bpp_zrodlo"})
    assert MyMultiseekResults._zapytanie_mnozy_wiersze(qs) is False


def test_pilnuje_ze_stala_pokrywa_oba_zrodla_duplikatow():
    assert MULTISEEK_MNOZACE_ZLACZENIA == {
        "bpp_autorzy_mat",
        "bpp_zewnetrzne_bazy_view",
    }


@pytest.mark.django_db
def test_realne_zapytanie_z_zewnetrznymi_bazami_mnozy():
    qs = Rekord.objects.filter(zewnetrzne_bazy__baza_id=1)
    assert MyMultiseekResults._zapytanie_mnozy_wiersze(qs) is True


@pytest.mark.django_db
def test_realne_zwykle_zapytanie_nie_mnozy():
    qs = Rekord.objects.all()
    assert MyMultiseekResults._zapytanie_mnozy_wiersze(qs) is False
