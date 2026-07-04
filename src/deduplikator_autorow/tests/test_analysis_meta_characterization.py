"""Charakteryzacyjne testy ``analiza_pary_meta``.

Pinują DOKŁADNE (score, reasons) dla reprezentatywnych wejść, tak aby
refaktoryzacja na tabelę reguł była gwarantowanie behavior-preserving.
Każdy assert sprawdza zarówno zwracany int, jak i pełną listę powodów
(w identycznej kolejności) — to jest właściwa charakteryzacja zachowania.
"""

from deduplikator_autorow.utils.analysis_meta import analiza_pary_meta


def _meta(
    nazwisko="kowalski",
    imiona=("jan",),
    orcid=None,
    tytul=False,
    tytul_id=None,
    pubs=0,
    lata=None,
):
    return {
        "nazwisko_norm": nazwisko,
        "nazwisko_parts": nazwisko.split("-"),
        "imiona_norm": list(imiona),
        "orcid_value": orcid,
        "ma_orcid": bool(orcid),
        "ma_tytul": tytul,
        "tytul_id": tytul_id if tytul_id is not None else (1 if tytul else None),
        "publikacje_count": pubs,
        "lata_publikacji": set(lata or []),
    }


# --- Para identyczna -------------------------------------------------------


def test_identyczna_para_domyslna():
    score, reasons = analiza_pary_meta(_meta(), _meta())
    assert score == 85
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Hard rejection: zupełnie różne imiona ---------------------------------


def test_hard_rejection_rozne_imiona():
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski", imiona=("agnieszka",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == -1000
    assert reasons == [
        "odrzucono: zupełnie różne imiona ('jan' vs 'agnieszka') — to różni autorzy"
    ]


# --- Gałęzie liczby publikacji ---------------------------------------------


def test_srednio_publikacji_6():
    score, reasons = analiza_pary_meta(_meta(pubs=6), _meta(pubs=6))
    assert score == 65
    assert reasons == [
        "średnio publikacji (6) - możliwy duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_wiele_publikacji_11():
    score, reasons = analiza_pary_meta(_meta(pubs=11), _meta(pubs=11))
    assert score == 55
    assert reasons == [
        "wiele publikacji (11) - mało prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Gałęzie tytułu naukowego ----------------------------------------------


def test_brak_tytulu_u_kandydata():
    score, reasons = analiza_pary_meta(_meta(tytul=True), _meta(tytul=False))
    assert score == 100
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "brak tytułu naukowego u kandydata - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_oba_maja_identyczny_tytul():
    a = _meta(tytul=True, tytul_id=5)
    b = _meta(tytul=True, tytul_id=5)
    score, reasons = analiza_pary_meta(a, b)
    assert score == 95
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczny tytuł naukowy",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_oba_maja_rozny_tytul():
    a = _meta(tytul=True, tytul_id=5)
    b = _meta(tytul=True, tytul_id=9)
    score, reasons = analiza_pary_meta(a, b)
    assert score == 70
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "różny tytuł naukowy",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Gałęzie ORCID ----------------------------------------------------------


def test_brak_orcid_u_kandydata():
    a = _meta(orcid="0000-0001-1111-1111")
    b = _meta(orcid=None)
    score, reasons = analiza_pary_meta(a, b)
    assert score == 100
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "brak ORCID u kandydata - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_identyczny_orcid():
    a = _meta(orcid="0000-0001-1111-1111")
    b = _meta(orcid="0000-0001-1111-1111")
    score, reasons = analiza_pary_meta(a, b)
    assert score == 135
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczny ORCID - to ten sam autor",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_rozny_orcid():
    a = _meta(imiona=("jan",), orcid="0000-0001-1111-1111")
    b = _meta(imiona=("jan",), orcid="0000-0002-2222-2222")
    score, reasons = analiza_pary_meta(a, b)
    assert score == 35
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "różny ORCID - to różni autorzy",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Gałęzie nazwiska -------------------------------------------------------


def test_nazwisko_zawieranie():
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski-nowak", imiona=("jan",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == 75
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "podobne nazwisko (zawieranie)",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_nazwisko_permutacja_czlonow():
    a = _meta(nazwisko="gal-cison", imiona=("jan",))
    b = _meta(nazwisko="cison-gal", imiona=("jan",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == 80
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne człony nazwiska złożonego (permutacja)",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


def test_nazwisko_wspolny_czlon():
    a = _meta(nazwisko="gal-cison", imiona=("jan",))
    b = _meta(nazwisko="gal-nowak", imiona=("jan",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == 65
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "wspólny człon nazwiska złożonego (gal)",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Swap imię ↔ nazwisko ---------------------------------------------------


def test_swap_imie_nazwisko():
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="jan", imiona=("kowalski",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == 60
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "wykryto pełną zamianę imienia z nazwiskiem",
    ]


# --- Podobne imię (3-prefix) ------------------------------------------------


def test_podobne_imie_3prefix():
    a = _meta(nazwisko="kowalski", imiona=("janusz",))
    b = _meta(nazwisko="kowalski", imiona=("janowski",))
    score, reasons = analiza_pary_meta(a, b)
    assert score == 70
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "podobne imię (1)",
        "pasujące inicjały (1)",
    ]


# --- Brak imion u kandydata (b puste, a niepuste) ---------------------------


def test_brak_imion_u_kandydata():
    a = _meta(imiona=("jan",))
    b = _meta(imiona=())
    score, reasons = analiza_pary_meta(a, b)
    assert score == 60
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "brak imion u kandydata",
    ]


# --- Gałęzie lat publikacji -------------------------------------------------


def test_wspolne_lata():
    a = _meta(lata=[2020, 2021])
    b = _meta(lata=[2021, 2022])
    score, reasons = analiza_pary_meta(a, b)
    assert score == 105
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
        "wspólne lata publikacji: [2021]",
    ]


def test_bliskie_lata():
    a = _meta(lata=[2020])
    b = _meta(lata=[2022])
    score, reasons = analiza_pary_meta(a, b)
    assert score == 100
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
        "bliskie lata publikacji (różnica 2)",
    ]


def test_srednia_odleglosc_lat():
    a = _meta(lata=[2020])
    b = _meta(lata=[2025])
    score, reasons = analiza_pary_meta(a, b)
    assert score == 80
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
        "średnia odległość lat publikacji (5)",
    ]


def test_duza_odleglosc_lat():
    a = _meta(lata=[2000])
    b = _meta(lata=[2020])
    score, reasons = analiza_pary_meta(a, b)
    assert score == 65
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
        "duża odległość lat publikacji (20)",
    ]


# --- Oba bez imion: brak gałęzi imion, brak hard-rejection ------------------


def test_oba_bez_imion():
    a = _meta(imiona=())
    b = _meta(imiona=())
    score, reasons = analiza_pary_meta(a, b)
    assert score == 50
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczne nazwisko",
    ]


# --- Brakujące klucze opcjonalne (.get fallbacks) + None tytul_id ----------


def test_brakujace_klucze_opcjonalne():
    """Bez ``nazwisko_parts`` / ``tytul_id`` / ``orcid_value`` w dict-cie.

    Pinuje fallbacki ``.get(...)``: brak ``nazwisko_parts`` → puste człony,
    a ``tytul_id`` nieobecne po obu stronach (None == None) → tytuł
    traktowany jako identyczny.
    """
    a = {
        "nazwisko_norm": "abcdef",
        "imiona_norm": ["jan"],
        "ma_orcid": False,
        "ma_tytul": True,
        "publikacje_count": 0,
        "lata_publikacji": set(),
    }
    b = {
        "nazwisko_norm": "xyzwvu",
        "imiona_norm": ["jan"],
        "ma_orcid": False,
        "ma_tytul": True,
        "publikacje_count": 0,
        "lata_publikacji": set(),
    }
    score, reasons = analiza_pary_meta(a, b)
    assert score == 55
    assert reasons == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "identyczny tytuł naukowy",
        "wspólne imię (1)",
        "pasujące inicjały (1)",
    ]
