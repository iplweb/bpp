import pytest

from import_pracownikow.parsers.osoba import (
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    rozbij_osobe,
)


def _tylko(*pary):
    dozwolone = {(i.strip(), n.strip()) for i, n in pary}
    return lambda im, nz: (im.strip(), nz.strip()) in dozwolone


def _bez(im, nz):
    return False


def _wszystko(im, nz):
    return True


PRZYPADKI = [
    # (tekst, tytuly, imiona_znane, probuj_match,
    #  tytul, imiona, nazwisko, confidence)
    (
        "dr Jan Kowalski",
        {"dr"},
        set(),
        _tylko(("Jan", "Kowalski")),
        "dr",
        "Jan",
        "Kowalski",
        CONF_HIGH,
    ),
    (
        "Jan Kowalski prof.",
        {"prof."},
        set(),
        _tylko(("Jan", "Kowalski")),
        "prof.",
        "Jan",
        "Kowalski",
        CONF_HIGH,
    ),
    (
        "Kowalska-Nowak, Anna Maria",
        set(),
        set(),
        _bez,
        None,
        "Anna Maria",
        "Kowalska-Nowak",
        CONF_HIGH,
    ),
    (
        "KOWALSKI Jan",
        set(),
        set(),
        _bez,
        None,
        "Jan",
        "KOWALSKI",
        CONF_HIGH,
    ),
    (
        "Anna Nowak",
        set(),
        set(),
        _tylko(("Anna", "Nowak")),
        None,
        "Anna",
        "Nowak",
        CONF_HIGH,
    ),
    (
        "Nowak Anna",
        set(),
        {"anna"},
        _bez,
        None,
        "Anna",
        "Nowak",
        CONF_MEDIUM,
    ),
    (
        "Anna Kowalska-Nowak",
        set(),
        set(),
        _bez,
        None,
        "Anna",
        "Kowalska-Nowak",
        CONF_MEDIUM,
    ),
    (
        "dr hab. Anna Maria Nowak",
        {"dr hab."},
        {"anna", "maria"},
        _bez,
        "dr hab.",
        "Anna Maria",
        "Nowak",
        CONF_MEDIUM,
    ),
    (
        "prof. dr hab. n. med. Jan Kowalski",
        {"prof. dr hab. n. med.", "dr", "prof."},
        set(),
        _tylko(("Jan", "Kowalski")),
        "prof. dr hab. n. med.",
        "Jan",
        "Kowalski",
        CONF_HIGH,
    ),
    (
        "Xyz Qwe",
        set(),
        set(),
        _bez,
        None,
        "Xyz",
        "Qwe",
        CONF_LOW,
    ),
    (
        "Jan Piotr",
        set(),
        set(),
        _wszystko,
        None,
        "Jan",
        "Piotr",
        CONF_LOW,
    ),
    (
        # A3: zdegenerowana komórka (jeden token) → puste imiona, całość jako
        # nazwisko, CONF_LOW. Pipeline i tak odrzuci to AutorForm-em (test w T6).
        "Kowalski",
        set(),
        set(),
        _bez,
        None,
        "",
        "Kowalski",
        CONF_LOW,
    ),
]


@pytest.mark.parametrize(
    "tekst,tytuly,imiona_znane,probuj,tytul,imiona,nazwisko,confidence",
    PRZYPADKI,
)
def test_rozbij_osobe_tabelarycznie(
    tekst, tytuly, imiona_znane, probuj, tytul, imiona, nazwisko, confidence
):
    wynik = rozbij_osobe(
        tekst, tytuly=tytuly, imiona_znane=imiona_znane, probuj_match=probuj
    )
    assert wynik.tytul == tytul
    assert wynik.imiona == imiona
    assert wynik.nazwisko == nazwisko
    assert wynik.confidence == confidence


def test_low_confidence_ma_alternatywe_odwroconej_kolejnosci():
    wynik = rozbij_osobe("Xyz Qwe", tytuly=set(), imiona_znane=set(), probuj_match=_bez)
    assert wynik.confidence == CONF_LOW
    assert wynik.alternatywy
    alt = wynik.alternatywy[0]
    assert alt["imiona"] == "Qwe"
    assert alt["nazwisko"] == "Xyz"


def test_wysoka_pewnosc_bez_alternatyw():
    wynik = rozbij_osobe(
        "Anna Nowak",
        tytuly=set(),
        imiona_znane=set(),
        probuj_match=_tylko(("Anna", "Nowak")),
    )
    assert wynik.confidence == CONF_HIGH
    assert wynik.alternatywy == []
