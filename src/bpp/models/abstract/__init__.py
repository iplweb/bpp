"""
Klasy abstrakcyjne

This package provides abstract models, mixins, and utilities for the BPP system.
"""

# Constants
# Abstracts
from .abstracts import (
    BazaModeluStreszczen,
)

# API Export
from .api_export import (
    ModelOpcjonalnieNieEksportowanyDoAPI,
)

# Author responsibility models
from .authors import (
    BazaModeluOdpowiedzialnosciAutorow,
    DodajAutoraMixin,
    MaProcentyMixin,
    NieMaProcentowMixin,
)
from .constants import (
    BRAK_PAGINACJI,
    IF_DECIMAL_PLACES,
    IF_MAX_DIGITS,
    ILOSC_ZNAKOW_NA_ARKUSZ,
    alt_strony_regex,
    parsed_informacje_regex,
    strony_regex,
    url_validator,
)

# Disciplines
from .disciplines import (
    ModelZPrzeliczaniemDyscyplin,
)

# Fees
from .fees import (
    ManagerModeliZOplataZaPublikacjeMixin,
    ModelZOplataZaPublikacje,
)

# Identifier models
from .identifiers import (
    ModelZDOI,
    ModelZISBN,
    ModelZISSN,
    ModelZPBN_ID,
    ModelZPubmedID,
)

# Keywords
from .keywords import (
    ModelZeSlowamiKluczowymi,
)

# Metadata models
from .metadata import (
    ModelZAdnotacjami,
    ModelZCharakterem,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZNumeremZeszytu,
)

# Naming models
from .naming import (
    DwaTytuly,
    ModelZNazwa,
    NazwaISkrot,
    NazwaWDopelniaczu,
)

# Open Access models
from .openaccess import (
    ModelZLiczbaCytowan,
    ModelZOpenAccess,
)

# PBN models
from .pbn import (
    LinkDoPBNMixin,
    ModelZPBN_UID,
)

# Publication base models
from .publication_base import (
    ModelRecenzowany,
    ModelTypowany,
    ModelZeZnakamiWydawniczymi,
    ModelZKonferencja,
    ModelZRokiem,
    ModelZSeria_Wydawnicza,
)

# Record base models
from .records import (
    ModelWybitny,
    RekordBPPBaza,
    Wydawnictwo_Baza,
)

# Scoring models
from .scoring import (
    POLA_PUNKTACJI,
    ModelPunktowany,
    ModelPunktowanyBaza,
    ModelZKwartylami,
)

# Search models
from .search import (
    ModelPrzeszukiwalny,
    ModelZLegacyData,
)

# Storage
from .storage import (
    ModelZMiejscemPrzechowywania,
)

# Utilities
from .utils import (
    ImpactFactorField,
    get_liczba_arkuszy_wydawniczych,
    nie_zawiera_adresu_doi_org,
    nie_zawiera_http_https,
    parse_informacje,
    parse_informacje_as_dict,
    wez_zakres_stron,
)

# Web/URL models
from .web import (
    ModelZAbsolutnymUrl,
    ModelZWWW,
)

# Define __all__ for explicit star imports
__all__ = [
    # Constants
    "BRAK_PAGINACJI",
    "IF_DECIMAL_PLACES",
    "IF_MAX_DIGITS",
    "ILOSC_ZNAKOW_NA_ARKUSZ",
    "POLA_PUNKTACJI",
    "alt_strony_regex",
    "parsed_informacje_regex",
    "strony_regex",
    "url_validator",
    # Utilities
    "ImpactFactorField",
    "get_liczba_arkuszy_wydawniczych",
    "nie_zawiera_adresu_doi_org",
    "nie_zawiera_http_https",
    "parse_informacje",
    "parse_informacje_as_dict",
    "wez_zakres_stron",
    # Models and Mixins
    "BazaModeluOdpowiedzialnosciAutorow",
    "BazaModeluStreszczen",
    "DodajAutoraMixin",
    "DwaTytuly",
    "LinkDoPBNMixin",
    "MaProcentyMixin",
    "ManagerModeliZOplataZaPublikacjeMixin",
    "ModelOpcjonalnieNieEksportowanyDoAPI",
    "ModelPrzeszukiwalny",
    "ModelPunktowany",
    "ModelPunktowanyBaza",
    "ModelRecenzowany",
    "ModelTypowany",
    "ModelWybitny",
    "ModelZAbsolutnymUrl",
    "ModelZAdnotacjami",
    "ModelZCharakterem",
    "ModelZDOI",
    "ModelZISBN",
    "ModelZISSN",
    "ModelZInformacjaZ",
    "ModelZKonferencja",
    "ModelZKwartylami",
    "ModelZLegacyData",
    "ModelZLiczbaCytowan",
    "ModelZMiejscemPrzechowywania",
    "ModelZNazwa",
    "ModelZNumeremZeszytu",
    "ModelZOpenAccess",
    "ModelZOplataZaPublikacje",
    "ModelZPBN_ID",
    "ModelZPBN_UID",
    "ModelZPrzeliczaniemDyscyplin",
    "ModelZPubmedID",
    "ModelZRokiem",
    "ModelZSeria_Wydawnicza",
    "ModelZWWW",
    "ModelZeStatusem",
    "ModelZeSlowamiKluczowymi",
    "ModelZeSzczegolami",
    "ModelZeZnakamiWydawniczymi",
    "NazwaISkrot",
    "NazwaWDopelniaczu",
    "NieMaProcentowMixin",
    "RekordBPPBaza",
    "Wydawnictwo_Baza",
]
