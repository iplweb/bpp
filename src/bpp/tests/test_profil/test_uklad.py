"""Testy rejestru sekcji i rozwiązywania układu profilu autora (czysta logika)."""

from types import SimpleNamespace

from bpp.profil_autora import (
    DOMYSLNY_LIMIT,
    KATALOG_SEKCJI,
    KLUCZ_BIOGRAM,
    KLUCZ_DYSCYPLINY,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_WYSZUKIWARKA,
    domyslny_uklad,
    rozwiaz_uklad,
    waliduj_uklad,
)


def _autor(uklad=None):
    return SimpleNamespace(uklad_profilu=uklad)


def _klucze(sekcje):
    return [s["klucz"] for s in sekcje]


def test_domyslny_uklad_pokrywa_caly_katalog():
    assert {s["klucz"] for s in domyslny_uklad()} == {t.klucz for t in KATALOG_SEKCJI}


def test_bez_konfiguracji_widoczne_sa_domyslne_sekcje():
    klucze = _klucze(rozwiaz_uklad(_autor(None)))
    assert KLUCZ_WYSZUKIWARKA in klucze
    assert KLUCZ_BIOGRAM in klucze
    # dyscypliny domyślnie wyłączone
    assert KLUCZ_DYSCYPLINY not in klucze


def test_wyszukiwarka_zawsze_widoczna():
    uklad = [{"klucz": KLUCZ_WYSZUKIWARKA, "widoczna": False, "limit": None}]
    assert KLUCZ_WYSZUKIWARKA in _klucze(rozwiaz_uklad(_autor(uklad)))


def test_konfiguracja_steruje_kolejnoscia():
    uklad = [
        {"klucz": KLUCZ_WYSZUKIWARKA, "widoczna": True, "limit": None},
        {"klucz": KLUCZ_BIOGRAM, "widoczna": True, "limit": None},
    ]
    klucze = _klucze(rozwiaz_uklad(_autor(uklad)))
    assert klucze.index(KLUCZ_WYSZUKIWARKA) < klucze.index(KLUCZ_BIOGRAM)


def test_ukrycie_sekcji_usuwa_ja():
    uklad = [{"klucz": KLUCZ_BIOGRAM, "widoczna": False, "limit": None}]
    assert KLUCZ_BIOGRAM not in _klucze(rozwiaz_uklad(_autor(uklad)))


def test_sekcja_spoza_configu_dolaczana_z_domyslem():
    # config zawiera tylko wyszukiwarkę; biogram (domyślnie ON) i tak ma się pojawić
    uklad = [{"klucz": KLUCZ_WYSZUKIWARKA, "widoczna": True, "limit": None}]
    assert KLUCZ_BIOGRAM in _klucze(rozwiaz_uklad(_autor(uklad)))


def test_waliduj_odrzuca_nieznany_klucz():
    assert waliduj_uklad([{"klucz": "xxx", "widoczna": True, "limit": None}]) == []


def test_waliduj_koryguje_niedozwolony_limit():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 7}])
    assert out[0]["limit"] == DOMYSLNY_LIMIT


def test_waliduj_akceptuje_dozwolony_limit():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 30}])
    assert out[0]["limit"] == 30


def test_waliduj_zeruje_limit_dla_sekcji_bez_limitu():
    out = waliduj_uklad([{"klucz": KLUCZ_BIOGRAM, "widoczna": True, "limit": 30}])
    assert out[0]["limit"] is None


def test_waliduj_deduplikuje_klucze():
    out = waliduj_uklad(
        [
            {"klucz": KLUCZ_BIOGRAM, "widoczna": True, "limit": None},
            {"klucz": KLUCZ_BIOGRAM, "widoczna": False, "limit": None},
        ]
    )
    assert len(out) == 1


def test_rozwiazane_sekcje_maja_nazwe_i_template():
    sekcja = rozwiaz_uklad(_autor(None))[0]
    assert sekcja["nazwa"]
    assert sekcja["template"].startswith("browse/autor_sekcje/")
