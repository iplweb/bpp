"""Testy rejestru sekcji i rozwiązywania układu profilu autora (czysta logika).

Podstrona autora to ciąg PASÓW: sekcja na całą szerokość albo para sekcji
„pół” obok siebie. ``rozwiaz_uklad`` czyta ``uczelnia.uklad_profilu_autora``
i zwraca płaską listę widocznych sekcji z szerokością; ``zloz_pasy`` paruje
(już wyrenderowane, niepuste) sekcje w pasy.
"""

from types import SimpleNamespace

from bpp.profil_autora import (
    DOMYSLNY_LIMIT,
    KATALOG_SEKCJI,
    KATALOG_WG_KLUCZA,
    KLUCZ_AFILIACJA,
    KLUCZ_DYSCYPLINY,
    KLUCZ_NAJLEPSZE_IF,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_PODSUMOWANIE,
    KLUCZ_RADON,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WIZYTOWKA,
    KLUCZ_WYKRESY,
    KLUCZ_WYSZUKIWARKA,
    LIMIT_LIST_PRAC,
    SZEROKOSC_CALA,
    SZEROKOSC_POL,
    domyslny_uklad,
    rozwiaz_uklad,
    waliduj_uklad,
    zloz_pasy,
)


def _uczelnia(uklad=None):
    return SimpleNamespace(uklad_profilu_autora=uklad)


def _klucze(sekcje):
    return [s["klucz"] for s in sekcje]


def _sekcja(klucz, szerokosc):
    return {"klucz": klucz, "szerokosc": szerokosc}


# --- rejestr / układ domyślny ----------------------------------------------


def test_domyslny_uklad_pokrywa_caly_katalog():
    assert {s["klucz"] for s in domyslny_uklad()} == {t.klucz for t in KATALOG_SEKCJI}


def test_domyslny_uklad_ma_szerokosc_per_katalog():
    for poz in domyslny_uklad():
        assert poz["szerokosc"] == KATALOG_WG_KLUCZA[poz["klucz"]].szerokosc


def test_domyslna_kolejnosc_i_szerokosci():
    # podsumowanie (cała) → wizytówka | afiliacja → wykresy (cała) → … →
    # wyszukiwarka (cała) pod sekcjami → listy prac parami.
    sekcje = rozwiaz_uklad(_uczelnia(None))
    klucze = _klucze(sekcje)
    assert klucze[:4] == [
        KLUCZ_PODSUMOWANIE,
        KLUCZ_WIZYTOWKA,
        KLUCZ_AFILIACJA,
        KLUCZ_WYKRESY,
    ]
    assert klucze.index(KLUCZ_WYSZUKIWARKA) < klucze.index(KLUCZ_NAJLEPSZE_PK)
    szer = {s["klucz"]: s["szerokosc"] for s in sekcje}
    assert szer[KLUCZ_PODSUMOWANIE] == SZEROKOSC_CALA
    assert szer[KLUCZ_WIZYTOWKA] == SZEROKOSC_POL
    assert szer[KLUCZ_AFILIACJA] == SZEROKOSC_POL
    assert szer[KLUCZ_WYKRESY] == SZEROKOSC_CALA
    assert szer[KLUCZ_WYSZUKIWARKA] == SZEROKOSC_CALA
    assert szer[KLUCZ_NAJLEPSZE_PK] == SZEROKOSC_POL
    assert szer[KLUCZ_NAJLEPSZE_IF] == SZEROKOSC_POL


def test_radon_na_cala_szerokosc():
    # RAD-on może zostać ukryty po stronie klienta — jako połówka zostawiłby
    # dziurę obok sąsiada.
    assert KATALOG_WG_KLUCZA[KLUCZ_RADON].szerokosc == SZEROKOSC_CALA


def test_domyslnie_wylaczone_sekcje_niewidoczne():
    assert KLUCZ_DYSCYPLINY not in _klucze(rozwiaz_uklad(_uczelnia(None)))


def test_brak_uczelni_dziala_jak_pusty_uklad():
    assert _klucze(rozwiaz_uklad(None)) == _klucze(rozwiaz_uklad(_uczelnia(None)))


def test_rozwiazane_sekcje_maja_komplet_pol():
    sekcja = rozwiaz_uklad(_uczelnia(None))[0]
    assert sekcja["nazwa"]
    assert sekcja["template"].startswith("browse/autor_sekcje/")
    assert sekcja["szerokosc"] in (SZEROKOSC_POL, SZEROKOSC_CALA)
    assert "template_only" in sekcja
    assert "karta" in sekcja


# --- konfiguracja ------------------------------------------------------------


def test_konfiguracja_steruje_kolejnoscia():
    uklad = [
        {"klucz": KLUCZ_WYKRESY, "widoczna": True},
        {"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": True},
    ]
    klucze = _klucze(rozwiaz_uklad(_uczelnia(uklad)))
    assert klucze.index(KLUCZ_WYKRESY) < klucze.index(KLUCZ_STATYSTYKI_CHARAKTER)


def test_konfiguracja_steruje_szerokoscia():
    uklad = [{"klucz": KLUCZ_WYKRESY, "szerokosc": SZEROKOSC_POL, "widoczna": True}]
    sekcje = rozwiaz_uklad(_uczelnia(uklad))
    wykresy = next(s for s in sekcje if s["klucz"] == KLUCZ_WYKRESY)
    assert wykresy["szerokosc"] == SZEROKOSC_POL


def test_ukrycie_sekcji():
    uklad = [{"klucz": KLUCZ_WYKRESY, "widoczna": False}]
    assert KLUCZ_WYKRESY not in _klucze(rozwiaz_uklad(_uczelnia(uklad)))


def test_sekcja_spoza_configu_doklejana_za_poprzednikiem_z_katalogu():
    # config zawiera tylko wykresy; podsumowanie (przed wykresami w katalogu)
    # ląduje przed nimi, statystyki (po wykresach) — za nimi.
    uklad = [{"klucz": KLUCZ_WYKRESY, "widoczna": True}]
    klucze = _klucze(rozwiaz_uklad(_uczelnia(uklad)))
    assert klucze.index(KLUCZ_PODSUMOWANIE) < klucze.index(KLUCZ_WYKRESY)
    assert klucze.index(KLUCZ_WYKRESY) < klucze.index(KLUCZ_STATYSTYKI_CHARAKTER)


# --- walidacja ---------------------------------------------------------------


def test_waliduj_uzupelnia_szerokosc_z_katalogu_gdy_brak():
    out = waliduj_uklad([{"klucz": KLUCZ_WYKRESY, "widoczna": True}])
    assert out[0]["szerokosc"] == SZEROKOSC_CALA


def test_waliduj_stary_zapis_z_kolumna_dostaje_domyslna_szerokosc():
    # back-compat: zapisy z czasów kolumn mają `kolumna`, nie `szerokosc`.
    out = waliduj_uklad(
        [{"klucz": KLUCZ_NAJLEPSZE_PK, "kolumna": "prawa", "widoczna": True}]
    )
    assert out[0]["szerokosc"] == SZEROKOSC_POL
    assert "kolumna" not in out[0]


def test_waliduj_odrzuca_klucze_sekcji_scalonych_w_grupy():
    # `biogram` / `identyfikatory` / `wykres_lata` weszły do grup
    # (wizytówka / afiliacja / wykresy) — stare zapisy nie wybuchają.
    out = waliduj_uklad(
        [
            {"klucz": "biogram", "widoczna": True},
            {"klucz": "identyfikatory", "widoczna": True},
            {"klucz": "wykres_lata", "widoczna": True},
        ]
    )
    assert out == []


def test_waliduj_koryguje_nieznana_szerokosc():
    out = waliduj_uklad([{"klucz": KLUCZ_WIZYTOWKA, "szerokosc": "1/3"}])
    assert out[0]["szerokosc"] == SZEROKOSC_POL


def test_waliduj_odrzuca_nieznany_klucz():
    assert waliduj_uklad([{"klucz": "xxx", "widoczna": True}]) == []


def test_waliduj_koryguje_niedozwolony_limit():
    # wartość zastępcza = domyślny limit TEJ sekcji (listy prac: 5)
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 7}])
    assert out[0]["limit"] == LIMIT_LIST_PRAC


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
            {"klucz": KLUCZ_WYKRESY, "widoczna": True},
            {"klucz": KLUCZ_WYKRESY, "widoczna": False},
        ]
    )
    assert len(out) == 1


def test_waliduj_pozycja_ma_kanoniczny_schemat():
    out = waliduj_uklad([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 30}])
    assert set(out[0].keys()) == {"klucz", "szerokosc", "widoczna", "limit"}


# --- parowanie w pasy --------------------------------------------------------


def test_zloz_pasy_paruje_kolejne_polowki():
    pasy = zloz_pasy(
        [
            _sekcja("a", SZEROKOSC_CALA),
            _sekcja("b", SZEROKOSC_POL),
            _sekcja("c", SZEROKOSC_POL),
            _sekcja("d", SZEROKOSC_CALA),
        ]
    )
    assert [_klucze(p) for p in pasy] == [["a"], ["b", "c"], ["d"]]


def test_zloz_pasy_samotna_polowka_przed_cala_stoi_sama():
    pasy = zloz_pasy(
        [
            _sekcja("a", SZEROKOSC_POL),
            _sekcja("b", SZEROKOSC_CALA),
            _sekcja("c", SZEROKOSC_POL),
        ]
    )
    assert [_klucze(p) for p in pasy] == [["a"], ["b"], ["c"]]


def test_zloz_pasy_trzy_polowki_daja_pare_i_samotna():
    pasy = zloz_pasy([_sekcja(k, SZEROKOSC_POL) for k in "abc"])
    assert [_klucze(p) for p in pasy] == [["a", "b"], ["c"]]


def test_zloz_pasy_pusta_lista():
    assert zloz_pasy([]) == []


def test_listy_prac_domyslnie_po_5_pozycji():
    from bpp.profil_autora import (
        KLUCZ_NAJNOWSZE_ARTYKULY,
        KLUCZ_NAJNOWSZE_ZWARTE,
        KLUCZ_OSTATNIO_EDYTOWANE,
        KLUCZ_WSPOLAUTORZY,
    )

    limity = {s["klucz"]: s["limit"] for s in rozwiaz_uklad(_uczelnia(None))}
    for klucz in (
        KLUCZ_NAJLEPSZE_PK,
        KLUCZ_NAJLEPSZE_IF,
        KLUCZ_NAJNOWSZE_ARTYKULY,
        KLUCZ_NAJNOWSZE_ZWARTE,
        KLUCZ_OSTATNIO_EDYTOWANE,
    ):
        assert limity[klucz] == LIMIT_LIST_PRAC
    # współautorzy — bez zmian
    assert limity[KLUCZ_WSPOLAUTORZY] == DOMYSLNY_LIMIT


def test_waliduj_akceptuje_limit_5():
    out = waliduj_uklad([{"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "limit": 5}])
    assert out[0]["limit"] is None  # sekcja bez limitu
    from bpp.profil_autora import KLUCZ_WSPOLAUTORZY

    out = waliduj_uklad([{"klucz": KLUCZ_WSPOLAUTORZY, "limit": 5}])
    assert out[0]["limit"] == 5


# --- sekcje elastyczne (np. wykresy) -----------------------------------------


def test_elastyczna_cala_dobiera_sie_do_samotnej_polowki():
    # Brak biogramu → afiliacja (pół) zostaje sama; wykresy (cała, elastyczne)
    # stają obok niej zamiast rozciągać afiliację na cały pas.
    pasy = zloz_pasy(
        [
            _sekcja("afiliacja", SZEROKOSC_POL),
            {**_sekcja("wykresy", SZEROKOSC_CALA), "elastyczna": True},
            _sekcja("statystyki", SZEROKOSC_POL),
        ]
    )
    assert [_klucze(p) for p in pasy] == [["afiliacja", "wykresy"], ["statystyki"]]


def test_elastyczna_bez_samotnej_polowki_zostaje_na_cala():
    pasy = zloz_pasy(
        [
            _sekcja("wizytowka", SZEROKOSC_POL),
            _sekcja("afiliacja", SZEROKOSC_POL),
            {**_sekcja("wykresy", SZEROKOSC_CALA), "elastyczna": True},
        ]
    )
    assert [_klucze(p) for p in pasy] == [["wizytowka", "afiliacja"], ["wykresy"]]


def test_zwykla_cala_nie_dobiera_sie_do_polowki():
    pasy = zloz_pasy([_sekcja("a", SZEROKOSC_POL), _sekcja("b", SZEROKOSC_CALA)])
    assert [_klucze(p) for p in pasy] == [["a"], ["b"]]


def test_wykresy_sa_elastyczne():
    sekcje = {s["klucz"]: s for s in rozwiaz_uklad(_uczelnia(None))}
    assert sekcje[KLUCZ_WYKRESY]["elastyczna"] is True
    assert sekcje[KLUCZ_AFILIACJA]["elastyczna"] is False
