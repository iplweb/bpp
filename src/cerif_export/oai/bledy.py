"""Błędy protokołu OAI-PMH 2.0.

Sześć kodów wymienionych w specyfikacji protokołu (sekcja 3.6). Wszystkie
zwracane są jako **XML z HTTP 200** — to nie pomyłka, tylko wymóg OAI-PMH:
błąd protokołu jest poprawną odpowiedzią repozytorium, a nie błędem HTTP.
Kody 4xx/5xx są zarezerwowane dla awarii transportu i po stronie harvestera
zwykle skutkują retry, a nie odczytaniem treści błędu.

Warstwa HTTP (``views.py``, Faza 2) serializuje wynik ``czasowniki.odpowiedz``
i zawsze odpowiada statusem 200 — poza wyłączeniem eksportu (404).
"""

from lxml import etree

# Namespace samego protokołu — NIE mylić z ``const.NS_OAI``, który jest
# namespace'em słowników OpenAIRE, ani z ``const.NS_CERIF`` (ładunek).
NS_PMH = "http://www.openarchives.org/OAI/2.0/"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

SCHEMA_LOCATION_PMH = (
    "http://www.openarchives.org/OAI/2.0/ "
    "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
)

KOD_BAD_VERB = "badVerb"
KOD_BAD_ARGUMENT = "badArgument"
KOD_CANNOT_DISSEMINATE_FORMAT = "cannotDisseminateFormat"
KOD_ID_DOES_NOT_EXIST = "idDoesNotExist"
KOD_NO_RECORDS_MATCH = "noRecordsMatch"
KOD_BAD_RESUMPTION_TOKEN = "badResumptionToken"

WSZYSTKIE_KODY = (
    KOD_BAD_VERB,
    KOD_BAD_ARGUMENT,
    KOD_CANNOT_DISSEMINATE_FORMAT,
    KOD_ID_DOES_NOT_EXIST,
    KOD_NO_RECORDS_MATCH,
    KOD_BAD_RESUMPTION_TOKEN,
)

# Przy tych dwóch kodach specyfikacja zabrania echowania atrybutów żądania
# w elemencie <request> — bo to właśnie one są niepoprawne. Zwracany jest
# sam baseURL.
KODY_BEZ_ECHA_ARGUMENTOW = frozenset({KOD_BAD_VERB, KOD_BAD_ARGUMENT})


class BladProtokolu(Exception):
    """Bazowy błąd protokołu OAI-PMH.

    Podklasa deklaruje ``kod``; warstwa czasowników zamienia wyjątek na
    element ``<error code="...">`` zamiast propagować go do HTTP.
    """

    kod = KOD_BAD_ARGUMENT
    komunikat_domyslny = "Niepoprawne żądanie OAI-PMH"

    def __init__(self, komunikat=None):
        self.komunikat = komunikat or self.komunikat_domyslny
        super().__init__(f"{self.kod}: {self.komunikat}")


class BlednyCzasownik(BladProtokolu):
    """``verb`` nie istnieje, brakuje go albo został powtórzony."""

    kod = KOD_BAD_VERB
    komunikat_domyslny = "Nieznany lub brakujący argument verb"


class BlednyArgument(BladProtokolu):
    """Argument nieznany, powtórzony, brakujący albo o złej składni."""

    kod = KOD_BAD_ARGUMENT
    komunikat_domyslny = "Niepoprawny zestaw argumentów"


class NieobslugiwanyFormat(BladProtokolu):
    """Żądany ``metadataPrefix`` nie jest obsługiwany przez repozytorium."""

    kod = KOD_CANNOT_DISSEMINATE_FORMAT
    komunikat_domyslny = "Nieobsługiwany metadataPrefix"


class NieznanyIdentyfikator(BladProtokolu):
    """Identyfikator nie daje się rozebrać albo nie ma za nim rekordu."""

    kod = KOD_ID_DOES_NOT_EXIST
    komunikat_domyslny = "Nieznany identyfikator rekordu"


class BrakPasujacychRekordow(BladProtokolu):
    """Kombinacja ``from``/``until``/``set``/``metadataPrefix`` jest pusta."""

    kod = KOD_NO_RECORDS_MATCH
    komunikat_domyslny = "Żaden rekord nie pasuje do podanych kryteriów"


class BlednyResumptionToken(BladProtokolu):
    """Token wygasł, ma zerwany podpis albo niekompletny ładunek."""

    kod = KOD_BAD_RESUMPTION_TOKEN
    komunikat_domyslny = "Resumption token jest niepoprawny lub wygasł"


WYJATKI_WG_KODU = {
    klasa.kod: klasa
    for klasa in (
        BlednyCzasownik,
        BlednyArgument,
        NieobslugiwanyFormat,
        NieznanyIdentyfikator,
        BrakPasujacychRekordow,
        BlednyResumptionToken,
    )
}


def element_bledu(kod: str, komunikat: str = "") -> etree._Element:
    """Zbuduj element ``<error code="...">`` w namespace protokołu.

    Podnosi ``ValueError`` dla kodu spoza specyfikacji — literówka w kodzie
    błędu jest po stronie harvestera nieodróżnialna od awarii repozytorium,
    więc lepiej wywalić się na miejscu niż wysłać niepoprawny XML.
    """
    if kod not in WSZYSTKIE_KODY:
        raise ValueError(f"Kod błędu spoza specyfikacji OAI-PMH: {kod!r}")

    element = etree.Element(f"{{{NS_PMH}}}error", code=kod)
    if komunikat:
        element.text = komunikat
    return element


def element_dla_wyjatku(wyjatek: BladProtokolu) -> etree._Element:
    """Zbuduj ``<error>`` z wyjątku protokołu."""
    return element_bledu(wyjatek.kod, wyjatek.komunikat)
