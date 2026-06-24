"""Testy rejestru sekcji i rozwiązywania układu profilu autora (czysta logika).

Po rewizji „konfigurowalny układ obu kolumn" KAŻDY element podstrony autora
(lewa i prawa kolumna) jest pozycją rejestru otagowaną kolumną. Układ jest
GLOBALNY per-Uczelnia: ``rozwiaz_uklad`` czyta ``uczelnia.uklad_profilu_autora``
i zwraca dict ``{"lewa": [...], "prawa": [...]}``.
"""

from types import SimpleNamespace

from bpp.profil_autora import (
    DOMYSLNY_LIMIT,
    KATALOG_SEKCJI,
    KATALOG_WG_KLUCZA,
    KLUCZ_BIOGRAM,
    KLUCZ_DYSCYPLINY,
    KLUCZ_IDENTYFIKATORY,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WYKRES_IF_LATA,
    KLUCZ_WYKRES_LATA,
    KLUCZ_WYKRES_PK_LATA,
    KLUCZ_WYSZUKIWARKA,
    KOLUMNA_LEWA,
    KOLUMNA_PRAWA,
    domyslny_uklad,
    rozwiaz_uklad,
    waliduj_uklad,
)


def _uczelnia(uklad=None):
    return SimpleNamespace(uklad_profilu_autora=uklad)


def _klucze(sekcje):
    return [s["klucz"] for s in sekcje]


def _wszystkie_klucze(uklad):
    return _klucze(uklad[KOLUMNA_LEWA]) + _klucze(uklad[KOLUMNA_PRAWA])


def test_domyslny_uklad_pokrywa_caly_katalog():
    assert {s["klucz"] for s in domyslny_uklad()} == {t.klucz for t in KATALOG_SEKCJI}


def test_domyslny_uklad_ma_kolumne_per_katalog():
    for poz in domyslny_uklad():
        assert poz["kolumna"] == KATALOG_WG_KLUCZA[poz["klucz"]].kolumna


def test_rejestr_obejmuje_obie_kolumny():
    # bloki lewej kolumny TERAZ są w katalogu (otagowane kolumną=lewa)
    klucze = {t.klucz for t in KATALOG_SEKCJI}
    assert KLUCZ_BIOGRAM in klucze
    assert KLUCZ_WYSZUKIWARKA in klucze
    assert KLUCZ_IDENTYFIKATORY in klucze
    assert KATALOG_WG_KLUCZA[KLUCZ_BIOGRAM].kolumna == KOLUMNA_LEWA
    assert KATALOG_WG_KLUCZA[KLUCZ_STATYSTYKI_CHARAKTER].kolumna == KOLUMNA_PRAWA


def test_rozwiaz_zwraca_dict_obu_kolumn():
    uklad = rozwiaz_uklad(_uczelnia(None))
    assert set(uklad.keys()) == {KOLUMNA_LEWA, KOLUMNA_PRAWA}
    assert isinstance(uklad[KOLUMNA_LEWA], list)
    assert isinstance(uklad[KOLUMNA_PRAWA], list)


def test_bez_konfiguracji_lewa_ma_znane_bloki():
    uklad = rozwiaz_uklad(_uczelnia(None))
    lewa = _klucze(uklad[KOLUMNA_LEWA])
    assert KLUCZ_BIOGRAM in lewa
    assert KLUCZ_IDENTYFIKATORY in lewa
    assert KLUCZ_WYSZUKIWARKA in lewa


def test_bez_konfiguracji_widoczne_sa_domyslne_sekcje_prawej():
    prawa = _klucze(rozwiaz_uklad(_uczelnia(None))[KOLUMNA_PRAWA])
    assert KLUCZ_STATYSTYKI_CHARAKTER in prawa
    assert KLUCZ_WYKRES_LATA in prawa
    assert KLUCZ_WYKRES_PK_LATA in prawa
    assert KLUCZ_WYKRES_IF_LATA in prawa
    # dyscypliny (statystyka) domyślnie wyłączone
    assert KLUCZ_DYSCYPLINY not in prawa


def test_domyslna_kolejnosc_lewej_odwzorowuje_dzisiejszy_uklad():
    lewa = _klucze(rozwiaz_uklad(_uczelnia(None))[KOLUMNA_LEWA])
    # zdjęcie/biogram na górze, wyszukiwarka po blokach tożsamości,
    # eksport na końcu — jak w dzisiejszym szablonie.
    assert lewa[0] == "zdjecie"
    assert lewa.index("biogram") < lewa.index("identyfikatory")
    assert lewa.index("identyfikatory") < lewa.index("wyszukiwarka")
    assert lewa.index("wyszukiwarka") < lewa.index("eksport")
    assert lewa[-1] == "eksport"


def test_brak_uczelni_dziala_jak_pusty_uklad():
    assert _wszystkie_klucze(rozwiaz_uklad(None)) == _wszystkie_klucze(
        rozwiaz_uklad(_uczelnia(None))
    )


def test_konfiguracja_steruje_kolejnoscia():
    uklad = [
        {"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None},
        {"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": True, "limit": None},
    ]
    prawa = _klucze(rozwiaz_uklad(_uczelnia(uklad))[KOLUMNA_PRAWA])
    assert prawa.index(KLUCZ_WYKRES_LATA) < prawa.index(KLUCZ_STATYSTYKI_CHARAKTER)


def test_przeniesienie_kolumny_przenosi_sekcje():
    # biogram (domyślnie lewa) przeniesiony do prawej musi wylądować w prawej.
    uklad = [{"klucz": KLUCZ_BIOGRAM, "kolumna": KOLUMNA_PRAWA, "widoczna": True}]
    res = rozwiaz_uklad(_uczelnia(uklad))
    assert KLUCZ_BIOGRAM in _klucze(res[KOLUMNA_PRAWA])
    assert KLUCZ_BIOGRAM not in _klucze(res[KOLUMNA_LEWA])


def test_ukrycie_sekcji_usuwa_ja_z_obu_kolumn():
    uklad = [{"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None}]
    assert KLUCZ_WYKRES_LATA not in _wszystkie_klucze(rozwiaz_uklad(_uczelnia(uklad)))


def test_sekcja_spoza_configu_dolaczana_z_domyslem_w_swojej_kolumnie():
    # config zawiera tylko wykres lat; statystyki (prawa, ON) i biogram (lewa,
    # ON) i tak mają się pojawić — w swoich domyślnych kolumnach.
    uklad = [{"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None}]
    res = rozwiaz_uklad(_uczelnia(uklad))
    assert KLUCZ_STATYSTYKI_CHARAKTER in _klucze(res[KOLUMNA_PRAWA])
    assert KLUCZ_BIOGRAM in _klucze(res[KOLUMNA_LEWA])


def test_waliduj_uzupelnia_kolumne_z_katalogu_gdy_brak():
    # back-compat: stary zapis bez `kolumna` — prawa sekcja dostaje "prawa".
    out = waliduj_uklad([{"klucz": KLUCZ_WYKRES_LATA, "widoczna": True}])
    assert out[0]["kolumna"] == KOLUMNA_PRAWA
    # lewa sekcja dostaje "lewa".
    out = waliduj_uklad([{"klucz": KLUCZ_BIOGRAM, "widoczna": True}])
    assert out[0]["kolumna"] == KOLUMNA_LEWA


def test_waliduj_koryguje_nieznana_kolumne_do_domyslnej():
    out = waliduj_uklad(
        [{"klucz": KLUCZ_BIOGRAM, "kolumna": "srodkowa", "widoczna": True}]
    )
    assert out[0]["kolumna"] == KOLUMNA_LEWA


def test_waliduj_akceptuje_jawna_kolumne():
    out = waliduj_uklad(
        [{"klucz": KLUCZ_BIOGRAM, "kolumna": KOLUMNA_PRAWA, "widoczna": True}]
    )
    assert out[0]["kolumna"] == KOLUMNA_PRAWA


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


def test_waliduj_pozycja_ma_kanoniczny_schemat():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 30}])
    assert set(out[0].keys()) == {"klucz", "kolumna", "widoczna", "limit"}


def test_rozwiazane_sekcje_maja_nazwe_template_i_kolumne():
    sekcja = rozwiaz_uklad(_uczelnia(None))[KOLUMNA_PRAWA][0]
    assert sekcja["nazwa"]
    assert sekcja["template"].startswith("browse/autor_sekcje/")
    assert sekcja["kolumna"] in (KOLUMNA_LEWA, KOLUMNA_PRAWA)
    assert "template_only" in sekcja
