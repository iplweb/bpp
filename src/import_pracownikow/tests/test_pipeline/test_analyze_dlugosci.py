"""Czytelny (PL) błąd długości w analizie — `_waliduj_dlugosci_pol`.

Przekroczenie `max_length` pola AutorForm ma dawać jasny polski komunikat
(arkusz/wiersz/pole/limit + „skróć"), zamiast surowego angielskiego
`Ensure this value has at most 200 characters` z `is_valid()`. Fail-fast
(odrzucamy plik) — spójne z resztą walidacji analizy.
"""

import pytest

from import_common.exceptions import XLSMatchError
from import_pracownikow.pipeline.analyze import _waliduj_dlugosci_pol


def _elem(**vals):
    # XLSMatchError.__str__ czyta __xls_loc_row__ (+1) i __xls_loc_sheet__.
    return {"__xls_loc_sheet__": 0, "__xls_loc_row__": 4, **vals}


def test_nazwisko_ponad_limit_daje_czytelny_polski_blad():
    dane = {"nazwisko": "x" * 250, "imię": "Jan"}
    with pytest.raises(XLSMatchError) as exc:
        _waliduj_dlugosci_pol(_elem(), dane)
    msg = str(exc.value)
    assert "250" in msg  # ile znaków ma wartość
    assert "200" in msg  # limit pola
    assert "skróć" in msg.lower()
    assert "wiersz nr 5" in msg  # 1-indexed (loc 4 + 1)


def test_wartosci_w_limicie_nie_rzucaja():
    # brak wyjątku = OK
    _waliduj_dlugosci_pol(_elem(), {"nazwisko": "Kowalski", "imię": "Jan"})


def test_blad_nazywa_pole_etykieta_z_pola_docelowego():
    with pytest.raises(XLSMatchError) as exc:
        _waliduj_dlugosci_pol(_elem(), {"tytuł_stopień": "d" * 300})
    assert "Tytuł" in str(exc.value)  # etykieta z POLA_DOCELOWE, nie surowy klucz


def test_pusta_i_none_pomijane():
    # puste/None nie wywalają (i tak nie przekraczają limitu)
    _waliduj_dlugosci_pol(_elem(), {"nazwisko": "", "tytuł_stopień": None})
