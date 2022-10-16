from collections import OrderedDict
from enum import Enum

TO_AUTOR = 0
TO_REDAKTOR = 1
TO_INNY = 2
TO_TLUMACZ = 3
TO_KOMENTATOR = 4
TO_RECENZENT = 5
TO_OPRACOWAL = 6
TO_REDAKTOR_TLUMACZENIA = 7

TYP_OGOLNY_DO_PBN = {
    TO_AUTOR: "AUTHOR",
    TO_REDAKTOR: "EDITOR",
    TO_TLUMACZ: "TRANSLATOR",
    TO_REDAKTOR_TLUMACZENIA: "TRANSLATION_EDITOR",
}

GR_WPROWADZANIE_DANYCH = "wprowadzanie danych"
GR_ZGLOSZENIA_PUBLIKACJI = "zgłoszenia publikacji"
GR_RAPORTY_WYSWIETLANIE = "generowanie raportów"
CHARAKTER_SLOTY_KSIAZKA = 1
CHARAKTER_SLOTY_ROZDZIAL = 2
CHARAKTER_SLOTY_REFERAT = 3

RODZAJ_PBN_ARTYKUL = 1
RODZAJ_PBN_ROZDZIAL = 2
RODZAJ_PBN_KSIAZKA = 3
RODZAJ_PBN_POSTEPOWANIE = 4

CHARAKTER_OGOLNY_ARTYKUL = "art"
CHARAKTER_OGOLNY_ROZDZIAL = "roz"
CHARAKTER_OGOLNY_KSIAZKA = "ksi"
CHARAKTER_OGOLNY_INNE = "xxx"


class DZIEDZINA(Enum):
    NAUKI_HUMANISTYCZNE = 1
    NAUKI_INZ_TECH = 2
    NAUKI_MEDYCZNE = 3
    NAUKI_ROLNICZE = 4
    NAUKI_SPOLECZNE = 5
    NAUKI_SCISLE = 6
    NAUKI_TEOLOGICZNE = 7
    NAUKI_SZTUKA = 8


WYZSZA_PUNKTACJA = [
    DZIEDZINA.NAUKI_SPOLECZNE,
    DZIEDZINA.NAUKI_HUMANISTYCZNE,
    DZIEDZINA.NAUKI_TEOLOGICZNE,
]

DZIEDZINY = OrderedDict()
DZIEDZINY[DZIEDZINA.NAUKI_HUMANISTYCZNE] = "Nauki humanistyczne"
DZIEDZINY[DZIEDZINA.NAUKI_INZ_TECH] = "Nauki inżynieryjno-techniczne"
DZIEDZINY[DZIEDZINA.NAUKI_MEDYCZNE] = "Nauki medyczne i o zdrowiu"
DZIEDZINY[DZIEDZINA.NAUKI_ROLNICZE] = "Nauki rolnicze"
DZIEDZINY[DZIEDZINA.NAUKI_SPOLECZNE] = "Nauki społeczne"
DZIEDZINY[DZIEDZINA.NAUKI_SCISLE] = "Nauki ścisłe i przyrodnicze"
DZIEDZINY[DZIEDZINA.NAUKI_TEOLOGICZNE] = "Nauki teologiczne"
DZIEDZINY[DZIEDZINA.NAUKI_SZTUKA] = "Sztuka"


class TRYB_KALKULACJI(Enum):
    AUTORSTWO_MONOGRAFII = 1
    REDAKCJA_MONOGRAFI = 2
    ROZDZIAL_W_MONOGRAFI = 3


class TRYB_DOSTEPU(Enum):
    NIEJAWNY = 0
    TYLKO_W_SIECI = 1
    JAWNY = 2


DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY = "jan_prev_then_current"
NAJWIEKSZY_REKORD = "max_rec"

PBN_UID_LEN = 24
ORCID_LEN = 19

LINK_PBN_DO_AUTORA = "{pbn_api_root}/core/#/person/view/{pbn_uid_id}/current"
LINK_PBN_DO_WYDAWCY = "{pbn_api_root}/core/#/publisher/view/{pbn_uid_id}/current"
LINK_PBN_DO_ZRODLA = "{pbn_api_root}/core/#/journal/view/{pbn_uid_id}/current"
LINK_PBN_DO_PUBLIKACJI = "{pbn_api_root}/core/#/publication/view/{pbn_uid_id}/current"

PBN_LATA = [
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
]

# Minimalny rok od którego zaczynamy liczyć punkty dla prac PBN i w ogóle minimalny rok integracji.
PBN_MIN_ROK = PBN_LATA[0]

# Maksymalny rok dla procedur eksportujących do PBN, liczącyc punkty/sloty oraz testów
PBN_MAX_ROK = PBN_LATA[-1]


KWARTYLE = [(None, "brak"), (1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]

WWW_FIELD_LABEL = "Adres WWW (płatny dostęp)"
PUBLIC_WWW_FIELD_LABEL = "Adres WWW (wolny dostęp)"
DOI_FIELD_LABEL = "DOI"
PBN_UID_FIELD_LABEL = "Odpowiednik w PBN"

ZDUBLOWANE_POLE_KOMUNIKAT = (
    'Uwaga, uwaga. W bazie danych istnieją inne rekordy z identycznym polem "{label}". '
    "Technicznie nie jest to błąd, ale mogą pojawić się problemy przy synchronizacji danych "
    "z systemami zewnętrznymi, np z bazą danych PBN."
)

PUSTY_ADRES_EMAIL = "brak@email.pl"

NUMER_ZGLOSZENIA_PARAM = "numer_zgloszenia"
CROSSREF_API_PARAM = "identyfikator_doi"
