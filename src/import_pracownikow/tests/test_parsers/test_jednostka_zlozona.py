import pytest

from import_pracownikow.parsers.jednostka_zlozona import _SKROT_RE, parsuj_komorke


@pytest.mark.parametrize(
    "komorka,skrot,nazwa,oddzial",
    [
        (
            "RW-1/1 Zakład Kierowania Działaniami Ratowniczymi, Działań "
            "Gaśniczych i Łączności WIBiOL taktyka",
            "RW-1/1",
            "Zakład Kierowania Działaniami Ratowniczymi, Działań Gaśniczych "
            "i Łączności",
            "WIBiOL",
        ),
        # ogon za oddziałem zawiera wielkoliterowe „RM"
        (
            "RW-7/1 Zakład Medycznych Działań Ratowniczych WIBiOL medyczne RM",
            "RW-7/1",
            "Zakład Medycznych Działań Ratowniczych",
            "WIBiOL",
        ),
        # brak ogona
        (
            "RW-6/3 Zakład Nauk Społecznych WIBiOL",
            "RW-6/3",
            "Zakład Nauk Społecznych",
            "WIBiOL",
        ),
        # RN — brak oddziału, ogon lowercase „instytut ib"
        (
            "RN-1 Instytut Inżynierii Bezpieczeństwa instytut ib",
            "RN-1",
            "Instytut Inżynierii Bezpieczeństwa",
            None,
        ),
        # łączniki „i"/„w"/„Ppoż." w środku nazwy
        (
            "RW-2/2 Zakład Hydromechaniki i Ppoż. Zaopatrzenia w Wodę WIBiOL "
            "hydra hydromechanika",
            "RW-2/2",
            "Zakład Hydromechaniki i Ppoż. Zaopatrzenia w Wodę",
            "WIBiOL",
        ),
        # skrót bez ukośnika
        (
            "RW-9 Studium Wychowania Fizycznego WIBiOL wf",
            "RW-9",
            "Studium Wychowania Fizycznego",
            "WIBiOL",
        ),
        # RN-2 — brak oddziału, ogon lowercase „instytut bw"
        (
            "RN-2 Instytut Bezpieczeństwa Wewnętrznego instytut bw",
            "RN-2",
            "Instytut Bezpieczeństwa Wewnętrznego",
            None,
        ),
        # RW-8 — oddział WIBiOL, ogon lowercase „języki"
        (
            "RW-8 Studium Języków Obcych WIBiOL języki",
            "RW-8",
            "Studium Języków Obcych",
            "WIBiOL",
        ),
        # RW-1/3 — skrót z ukośnikiem, oddział WIBiOL, ogon „ratchem chemiczne"
        (
            "RW-1/3 Zakład Bezpieczeństwa Działań i Ratownictwa Technicznego "
            "WIBiOL ratchem chemiczne",
            "RW-1/3",
            "Zakład Bezpieczeństwa Działań i Ratownictwa Technicznego",
            "WIBiOL",
        ),
        # pusta komórka
        ("", None, "", None),
    ],
)
def test_parsuj_komorke(komorka, skrot, nazwa, oddzial):
    wynik = parsuj_komorke(komorka)
    assert wynik["skrot"] == skrot
    assert wynik["nazwa"] == nazwa
    assert wynik["oddzial"] == oddzial


# Wszystkie 31 unikalnych wartości komórek z próbki APOŻ (spec §7/§14) —
# self-contained, bez dostępu do ~/Downloads/struktura.xlsx.
WSZYSTKIE_KOMORKI = [
    "RN-1 Instytut Inżynierii Bezpieczeństwa instytut ib",
    "RN-2 Instytut Bezpieczeństwa Wewnętrznego instytut bw",
    "RW-1 Katedra Działań Ratowniczych WIBiOL rat",
    (
        "RW-1/1 Zakład Kierowania Działaniami Ratowniczymi, Działań "
        "Gaśniczych i Łączności WIBiOL taktyka"
    ),
    "RW-1/2 Zakład Ratownictwa Chemicznego i Ekologicznego WIBiOL taktyka",
    (
        "RW-1/3 Zakład Bezpieczeństwa Działań i Ratownictwa "
        "Technicznego WIBiOL ratchem chemiczne"
    ),
    "RW-2 Katedra Techniki Pożarniczej WIBiOL technika",
    "RW-2/1 Zakład Mechaniki Stosowanej WIBiOL mechanika",
    (
        "RW-2/2 Zakład Hydromechaniki i Ppoż. Zaopatrzenia w Wodę "
        "WIBiOL hydra hydromechanika"
    ),
    "RW-2/3 Zakład Sprzętu Ratowniczego WIBiOL sprzęt",
    "RW-2/4 Zakład Elektroenergetyki WIBiOL elektroenergetyka",
    "RW-3 Katedra Przeciwdziałania Zagrożeniom WIBiOL bezpieczeństwo",
    (
        "RW-3/1 Zakład Bezpieczeństwa Pożarowego Budynków i Budowli "
        "Ochronnych WIBiOL bezpieczeństwo budynków"
    ),
    "RW-3/2 Zakład Podstaw Budownictwa i Materiałów Budowlanych WIBiOL budownictwo",
    "RW-3/3 Zakład Technicznych Systemów Zabezpieczeń WIBiOL tsz",
    "RW-4 Katedra Nauk Ścisłych WIBiOL ścisłe",
    "RW-4/1 Zakład Matematyki i Informatyki WIBiOL matematyka informatyka",
    "RW-4/2 Zakład Fizyki i Chemii WIBiOL fizyka chemia",
    "RW-5 Katedra Procesów Spalania WIBiOL spalanie wybuchy gaszenie",
    "RW-5/1 Zakład Teorii Procesów Spalania i Wybuchu WIBiOL spalanie",
    "RW-5/2 Zakład Środków Gaśniczych i Neutralizujących WIBiOL środki",
    "RW-5/3 Zakład Badania Przyczyn Pożarów i Rozpoznawania Zagrożeń WIBiOL pożary",
    "RW-6 Katedra Ochrony Ludności i Obrony Cywilnej WIBiOL bezp",
    "RW-6/1 Zakład Zintegrowanych Systemów Bezpieczeństwa WIBiOL bezp",
    "RW-6/2 Zakład Bezpieczeństwa Wewnętrznego WIBiOL bezp",
    "RW-6/3 Zakład Nauk Społecznych WIBiOL",
    "RW-7 Katedra Ratownictwa Medycznego WIBiOL społ",
    "RW-7/1 Zakład Medycznych Działań Ratowniczych WIBiOL medyczne RM",
    "RW-7/2 Zakład Medycyny Ratunkowej WIBiOL medyczne RM",
    "RW-8 Studium Języków Obcych WIBiOL języki",
    "RW-9 Studium Wychowania Fizycznego WIBiOL wf",
]


@pytest.mark.parametrize("komorka", WSZYSTKIE_KOMORKI)
def test_parsuj_komorke_invarianty(komorka):
    """Invarianty na wszystkich 31 wartościach (bez dokładnych oczekiwań):
    skrót pasuje do wzorca albo None; oddział ∈ {WIBiOL, None}; nazwa niepusta
    i nie zaczyna się od tokenu skrótu."""
    wynik = parsuj_komorke(komorka)
    assert wynik["skrot"] is None or _SKROT_RE.match(wynik["skrot"])
    assert wynik["oddzial"] in {"WIBiOL", None}
    assert wynik["nazwa"] != ""
    if wynik["skrot"] is not None:
        assert not wynik["nazwa"].startswith(wynik["skrot"])
