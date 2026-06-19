"""Testy rejestru sekcji i rozwiązywania układu profilu autora (czysta logika).

Po rewizji 2-kolumnowej układ jest GLOBALNY per-Uczelnia (a nie per-autor):
``rozwiaz_uklad`` czyta ``uczelnia.uklad_profilu_autora``. Rejestr obsługuje
wyłącznie sekcje PRAWEJ kolumny — biogram i wyszukiwarka są stałe w lewej
kolumnie szablonu, więc zniknęły z katalogu.
"""

from types import SimpleNamespace

from bpp.profil_autora import (
    DOMYSLNY_LIMIT,
    KATALOG_SEKCJI,
    KLUCZ_DYSCYPLINY,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WYKRES_IF_LATA,
    KLUCZ_WYKRES_LATA,
    KLUCZ_WYKRES_PK_LATA,
    domyslny_uklad,
    rozwiaz_uklad,
    waliduj_uklad,
)


def _uczelnia(uklad=None):
    return SimpleNamespace(uklad_profilu_autora=uklad)


def _klucze(sekcje):
    return [s["klucz"] for s in sekcje]


def test_domyslny_uklad_pokrywa_caly_katalog():
    assert {s["klucz"] for s in domyslny_uklad()} == {t.klucz for t in KATALOG_SEKCJI}


def test_rejestr_obejmuje_tylko_prawa_kolumne():
    # biogram / wyszukiwarka / eksport są w lewej kolumnie (stałe) lub w Fazie 2
    klucze = {t.klucz for t in KATALOG_SEKCJI}
    assert "biogram" not in klucze
    assert "wyszukiwarka" not in klucze
    assert "eksport" not in klucze


def test_typ_sekcji_nie_ma_juz_pola_obowiazkowa():
    assert not hasattr(KATALOG_SEKCJI[0], "obowiazkowa")


def test_bez_konfiguracji_widoczne_sa_domyslne_sekcje():
    klucze = _klucze(rozwiaz_uklad(_uczelnia(None)))
    assert KLUCZ_STATYSTYKI_CHARAKTER in klucze
    assert KLUCZ_WYKRES_LATA in klucze
    assert KLUCZ_WYKRES_PK_LATA in klucze
    assert KLUCZ_WYKRES_IF_LATA in klucze
    # dyscypliny domyślnie wyłączone
    assert KLUCZ_DYSCYPLINY not in klucze


def test_brak_uczelni_dziala_jak_pusty_uklad():
    assert _klucze(rozwiaz_uklad(None)) == _klucze(rozwiaz_uklad(_uczelnia(None)))


def test_konfiguracja_steruje_kolejnoscia():
    uklad = [
        {"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None},
        {"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": True, "limit": None},
    ]
    klucze = _klucze(rozwiaz_uklad(_uczelnia(uklad)))
    assert klucze.index(KLUCZ_WYKRES_LATA) < klucze.index(KLUCZ_STATYSTYKI_CHARAKTER)


def test_ukrycie_sekcji_usuwa_ja():
    uklad = [{"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None}]
    assert KLUCZ_WYKRES_LATA not in _klucze(rozwiaz_uklad(_uczelnia(uklad)))


def test_sekcja_spoza_configu_dolaczana_z_domyslem():
    # config zawiera tylko wykres lat; statystyki (domyślnie ON) i tak mają się pojawić
    uklad = [{"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None}]
    assert KLUCZ_STATYSTYKI_CHARAKTER in _klucze(rozwiaz_uklad(_uczelnia(uklad)))


def test_waliduj_odrzuca_nieznany_klucz():
    assert waliduj_uklad([{"klucz": "xxx", "widoczna": True, "limit": None}]) == []


def test_waliduj_koryguje_niedozwolony_limit():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 7}])
    assert out[0]["limit"] == DOMYSLNY_LIMIT


def test_waliduj_akceptuje_dozwolony_limit():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 30}])
    assert out[0]["limit"] == 30


def test_waliduj_zeruje_limit_dla_sekcji_bez_limitu():
    out = waliduj_uklad(
        [{"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": True, "limit": 30}]
    )
    assert out[0]["limit"] is None


def test_waliduj_deduplikuje_klucze():
    out = waliduj_uklad(
        [
            {"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None},
            {"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None},
        ]
    )
    assert len(out) == 1


def test_rozwiazane_sekcje_maja_nazwe_i_template():
    sekcja = rozwiaz_uklad(_uczelnia(None))[0]
    assert sekcja["nazwa"]
    assert sekcja["template"].startswith("browse/autor_sekcje/")
