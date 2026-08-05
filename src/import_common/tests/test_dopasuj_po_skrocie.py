"""Testy czystego matchera jednostek po skrótach słów (bez DB)."""

from types import SimpleNamespace

from import_common.core.jednostka import (
    _jest_numeralem,
    _liczba_dopasowanych,
    _para_prefiksowa,
    _slowa,
    dopasuj_po_skrocie,
)


def _kand(nazwa, skrot, sim=0.5):
    return SimpleNamespace(nazwa=nazwa, skrot=skrot, sim=sim)


# --- _slowa --------------------------------------------------------------------


def test_slowa_normalizuje_i_obcina_kropki():
    assert _slowa("Zakład Piel. Anestezjol.") == ["zaklad", "piel", "anestezjol"]


def test_slowa_usuwa_nawiasowy_skrot_wydzialu():
    # '(WNoZ)' to skrót wydziału — ma zniknąć, nie stać się tokenem 'wnoz'
    assert _slowa("Zakład Pielęgniarstwa (WNoZ)") == ["zaklad", "pielegniarstwa"]


def test_slowa_obcina_transliterowane_cudzyslowy():
    # unidecode('„')==',,' , unidecode('»')=='>>' — brzegi mają zniknąć
    assert _slowa("„FizjoPasjonaci” »SKN«") == ["fizjopasjonaci", "skn"]


def test_slowa_pusty():
    assert _slowa("") == []
    assert _slowa("   ") == []


# --- _jest_numeralem -----------------------------------------------------------


def test_jest_numeralem():
    assert _jest_numeralem("vii") is True
    assert _jest_numeralem("VIII") is True
    assert _jest_numeralem("iii") is True
    assert _jest_numeralem("12") is True
    assert _jest_numeralem("med") is False
    assert _jest_numeralem("lic") is False  # L/I/C, ale nie poprawny numerał


# --- _para_prefiksowa ----------------------------------------------------------


def test_para_prefiksowa_dwukierunkowa():
    assert _para_prefiksowa("piel", "pielegniarstwa") is True
    assert _para_prefiksowa("pielegniarstwa", "piel") is True
    assert _para_prefiksowa("med", "medycznej") is True


def test_para_prefiksowa_krotkie_wymagaja_rownosci():
    # 'i' (≤2) nie może być prefiksem 'intensywnej'
    assert _para_prefiksowa("i", "intensywnej") is False
    assert _para_prefiksowa("i", "i") is True
    assert _para_prefiksowa("ii", "ii") is True


def test_para_prefiksowa_numeraly_wymagaja_rownosci():
    # VII nie może być prefiksem VIII (numerowane kliniki)
    assert _para_prefiksowa("vii", "viii") is False
    assert _para_prefiksowa("xii", "xiii") is False
    assert _para_prefiksowa("vii", "vii") is True


def test_para_prefiksowa_rozne():
    assert _para_prefiksowa("chirurgii", "biologii") is False


# --- _liczba_dopasowanych ------------------------------------------------------


def test_liczba_dopasowanych_pelne_wyrownanie():
    plik = ["zaklad", "piel", "anestezjol", "i", "intens", "opieki", "medycznej"]
    pole = [
        "zaklad",
        "pielegniarstwa",
        "anestezjologicznego",
        "i",
        "intensywnej",
        "opieki",
        "medycznej",
    ]
    assert _liczba_dopasowanych(plik, pole) == 7


def test_liczba_dopasowanych_podciag_z_pominietymi_slowami_pola():
    # plik bez 'i' — pole ma 'i'; podciąg nadal się domyka
    plik = ["kat", "zakl", "zdr", "publ"]
    pole = ["katedra", "i", "zaklad", "zdrowia", "publicznego"]
    assert _liczba_dopasowanych(plik, pole) == 4


def test_liczba_dopasowanych_nieznane_slowo_pliku_none():
    assert _liczba_dopasowanych(["zaklad", "chirurgii"], ["zaklad", "biologii"]) is None


def test_liczba_dopasowanych_plik_dluzszy_niz_pole_none():
    plik = ["zaklad", "piel", "anestezjol", "i", "intens", "opieki", "medycznej"]
    assert _liczba_dopasowanych(plik, ["zaklad", "opieki"]) is None


# --- dopasuj_po_skrocie --------------------------------------------------------


def test_dopasuj_zgloszony_przypadek():
    kand = _kand(
        "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej",
        "Zakł. Piel. Anestezj.",
        sim=0.629,
    )
    wynik = dopasuj_po_skrocie(
        "Zakład Piel. Anestezjol. i Intens. Opieki Medycznej", [kand]
    )
    assert wynik is kand


def test_dopasuj_dwukierunkowo_plik_pelny_pole_skrocone():
    # plik pełny; dopasowanie przez skrócone słowa w NAZWIE kandydata,
    # pokrycie liczone względem nazwy (5 słów) = 5/5
    kand = _kand("Kat. i Zakł. Zdr. Publ.", "KZP", sim=0.4)
    wynik = dopasuj_po_skrocie("Katedra i Zakład Zdrowia Publicznego", [kand])
    assert wynik is kand


def test_dopasuj_min_slow_jedno_slowo_none():
    kand = _kand("Zakład Pielęgniarstwa Opieki", "ZPO", sim=0.5)
    assert dopasuj_po_skrocie("Piel.", [kand]) is None


def test_dopasuj_guard_pokrycia_fragment_none():
    # 3 słowa pliku vs 7 słów NAZWY → pokrycie 3/7=0.43 < 0.6 → odrzucony,
    # nawet gdy skrót kandydata jest krótki (guard liczy się względem nazwy)
    kand = _kand(
        "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej",
        "Zakł. Piel. Anestezj.",
        sim=0.4,
    )
    assert dopasuj_po_skrocie("Zakład Opieki Medycznej", [kand]) is None


def test_dopasuj_krotki_skrot_nie_omija_guardu():
    # regres na finding #1: 2-słowny generyk vs krótki skrot NIE może przejść
    kand = _kand(
        "Zakład Chorób Wewnętrznych i Metabolicznych", "Zakł. Chor. Wewn.", sim=0.4
    )
    # pokrycie względem nazwy: 2/5 = 0.4 < 0.6 (a NIE 2/3 względem skrotu)
    assert dopasuj_po_skrocie("Zakład Chorób", [kand]) is None


def test_dopasuj_dopisek_w_pliku_none():
    # all-or-nothing na słowach pliku: dopisek 'UM' bez pary → None (znany limit v1)
    kand = _kand("Zakład Transfuzjologii", "ZT", sim=0.5)
    assert dopasuj_po_skrocie("Zakład Transfuzjologii UM", [kand]) is None


def test_dopasuj_wybiera_najlepsze_pokrycie_potem_sim():
    # słaby: 4 słowa nazwy → pokrycie 3/4=0.75; mocny: 3 słowa → 3/3=1.0
    slaby = _kand("Zakład Opieki Zdrowotnej Medycznej", "ZOZM", sim=0.9)
    mocny = _kand("Zakład Opieki Medycznej", "ZOM", sim=0.3)
    wynik = dopasuj_po_skrocie("Zakład Opieki Medycznej", [slaby, mocny])
    assert wynik is mocny


def test_dopasuj_brak_kandydatow_none():
    assert dopasuj_po_skrocie("Zakład Czegokolwiek", []) is None
