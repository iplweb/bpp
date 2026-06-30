"""Charakteryzacyjne testy dla pbn_extras.parse_historia_komunikatow.

Pinują OBECNE zachowanie parsera tekstu historii komunikatów PBN, aby
umożliwić bezpieczny refactor (zdjęcie C901).
"""

from datetime import datetime

from pbn_api.templatetags.pbn_extras import (
    parse_historia_komunikatow,
    parse_timestamp,
)

TS1 = "2025-09-04 19:40:42.324808+00:00"
TS2 = "2025-09-05 10:00:00.000001+00:00"


def test_pusty_tekst_zwraca_pusta_liste():
    assert parse_historia_komunikatow("") == []
    assert parse_historia_komunikatow(None) == []


def test_pojedyncza_wiadomosc_info():
    text = f"{TS1}\nJakas tresc komunikatu"
    result = parse_historia_komunikatow(text)
    assert len(result) == 1
    msg = result[0]
    assert msg["timestamp"] == TS1
    assert msg["datetime"] == datetime(2025, 9, 4, 19, 40, 42)
    assert msg["content"] == "Jakas tresc komunikatu"
    assert msg["type"] == "info"
    assert msg["is_traceback"] is False


def test_linia_separatora_jest_pomijana():
    text = f"{TS1}\n===========\nTresc po separatorze"
    result = parse_historia_komunikatow(text)
    assert len(result) == 1
    assert result[0]["content"] == "Tresc po separatorze"


def test_typ_error_z_bledu():
    text = f"{TS1}\nWystapil błąd podczas wysylki"
    assert parse_historia_komunikatow(text)[0]["type"] == "error"


def test_typ_error_z_error_i_traceback():
    assert parse_historia_komunikatow(f"{TS1}\nAn error happened")[0]["type"] == "error"
    assert (
        parse_historia_komunikatow(f"{TS1}\nlowercase traceback here")[0]["type"]
        == "error"
    )


def test_typ_success():
    text = f"{TS1}\nWyslano pomyślnie do PBN"
    assert parse_historia_komunikatow(text)[0]["type"] == "success"


def test_typ_warning_autoryzacja():
    text = f"{TS1}\nBlad autoryzacji uzytkownika"
    assert parse_historia_komunikatow(text)[0]["type"] == "warning"


def test_typ_resend():
    text = f"{TS1}\nponownie wysłano dane"
    assert parse_historia_komunikatow(text)[0]["type"] == "resend"


def test_typ_ostatnia_linia_wygrywa():
    # Type jest ustawiany per-linia w łańcuchu if/elif, więc OSTATNIA
    # pasująca linia nadpisuje poprzednie.
    text = f"{TS1}\nWystapil błąd\nale ostatecznie pomyślnie zakonczono"
    assert parse_historia_komunikatow(text)[0]["type"] == "success"


def test_wiele_wiadomosci_sortowanych_najnowsze_pierwsze():
    text = f"{TS1}\nStarsza wiadomosc\n{TS2}\nNowsza wiadomosc"
    result = parse_historia_komunikatow(text)
    assert len(result) == 2
    assert result[0]["timestamp"] == TS2
    assert result[0]["content"] == "Nowsza wiadomosc"
    assert result[1]["timestamp"] == TS1
    assert result[1]["content"] == "Starsza wiadomosc"


def test_is_traceback_wykrywa_duze_T():
    text = f"{TS1}\nTraceback (most recent call last):\n  File foo"
    msg = parse_historia_komunikatow(text)[0]
    assert msg["is_traceback"] is True
    assert msg["type"] == "error"
    # Każda linia jest .strip()owana, więc wcięcie "  File foo" znika.
    assert msg["content"] == "Traceback (most recent call last):\nFile foo"


def test_tresc_przed_pierwszym_timestampem_ignorowana():
    text = "Tresc bez timestampu\nwiecej tresci"
    assert parse_historia_komunikatow(text) == []


def test_timestamp_bez_tresci_pomijany():
    text = f"{TS1}\n{TS2}\nTylko druga ma tresc"
    result = parse_historia_komunikatow(text)
    assert len(result) == 1
    assert result[0]["timestamp"] == TS2


def test_wielolinijkowa_tresc_laczona():
    text = f"{TS1}\nLinia 1\nLinia 2\nLinia 3"
    assert parse_historia_komunikatow(text)[0]["content"] == "Linia 1\nLinia 2\nLinia 3"


def test_parse_timestamp_poprawny():
    assert parse_timestamp(TS1) == datetime(2025, 9, 4, 19, 40, 42)


def test_parse_timestamp_niepoprawny_zwraca_none():
    assert parse_timestamp("to nie jest data") is None
