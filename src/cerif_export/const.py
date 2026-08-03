"""Stałe profilu OpenAIRE Guidelines for CRIS Managers 1.2.0.

Wszystko, co jest literałem wynikającym wprost ze specyfikacji profilu,
siedzi tutaj — żeby przy podbiciu wersji profilu było jedno miejsce do
zmiany.
"""

import datetime

METADATA_PREFIX = "oai_cerif_openaire"

NS_CERIF = "https://www.openaire.eu/cerif-profile/1.2/"
NS_OAI = "http://www.openaire.eu/cerif-profile/vocab/"
NS_COAR_ACCESS = "http://purl.org/coar/access_right"
NS_COAR_PUBLICATION_TYPES = (
    "https://www.openaire.eu/cerif-profile/vocab/COAR_Publication_Types"
)
NS_COAR_PATENT_TYPES = "https://www.openaire.eu/cerif-profile/vocab/COAR_Patent_Types"

NSMAP = {
    None: NS_CERIF,
    "coar_access": NS_COAR_ACCESS,
}

# Dziewięć setów wymaganych przez profil. Muszą istnieć nawet puste —
# wytyczne mówią wprost "even if unpopulated".
SET_PUBLICATIONS = "openaire_cris_publications"
SET_PRODUCTS = "openaire_cris_products"
SET_PATENTS = "openaire_cris_patents"
SET_PERSONS = "openaire_cris_persons"
SET_ORGUNITS = "openaire_cris_orgunits"
SET_PROJECTS = "openaire_cris_projects"
SET_FUNDING = "openaire_cris_funding"
SET_EVENTS = "openaire_cris_events"
SET_EQUIPMENTS = "openaire_cris_equipments"

WSZYSTKIE_SETY = (
    SET_PUBLICATIONS,
    SET_PRODUCTS,
    SET_PATENTS,
    SET_PERSONS,
    SET_ORGUNITS,
    SET_PROJECTS,
    SET_FUNDING,
    SET_EVENTS,
    SET_EQUIPMENTS,
)

# setName jest przez profil USTALONY co do znaku: walidator porównuje go
# dosłownie z "OpenAIRE_CRIS_<sufiks>" (kontrola check020_Sets). To NIE jest
# etykieta do tłumaczenia — pierwotnie siedziały tu polskie opisy i walidator
# odrzucił je komunikatem "Non-matching set name".
PREFIKS_NAZWY_SETU = "OpenAIRE_CRIS_"


def nazwa_setu(set_spec: str) -> str:
    """Kanoniczna nazwa setu wymagana przez profil."""
    return PREFIKS_NAZWY_SETU + set_spec.removeprefix("openaire_cris_")


# Typy encji CERIF używane jako człon identyfikatora OAI.
TYP_PUBLICATION = "Publications"
TYP_PERSON = "Persons"
TYP_ORGUNIT = "OrgUnits"
TYP_PATENT = "Patents"
TYP_EVENT = "Events"
TYP_SERVICE = "Services"

# Format datestampów OAI-PMH deklarowany w Identify. Wszystkie znaczniki
# czasu wychodzą w UTC w tym formacie.
GRANULARITY = "YYYY-MM-DDThh:mm:ssZ"
FORMAT_DATESTAMP = "%Y-%m-%dT%H:%M:%SZ"

# Wartość zastępcza dla rekordów z ostatnio_zmieniony IS NULL. Używana
# zarówno do sortowania keyset, jak i w nagłówku <datestamp> — bez tego
# rekordy z NULL-em wypadłyby z paginacji i nie trafiły do harvestu.
EPOKA = "1970-01-01T00:00:00Z"
EPOKA_DT = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)

ROZMIAR_STRONY = 100

# Czas życia resumption tokenu (sekundy).
TOKEN_TTL = 24 * 60 * 60
TOKEN_SALT = "cerif_export.resumption"

DELETED_RECORD = "no"
