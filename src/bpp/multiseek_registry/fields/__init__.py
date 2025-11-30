"""Multiseek query objects for BPP search functionality.

This package provides backward compatibility - all classes and functions
that were previously in fields.py are re-exported here.
"""

from django.conf import settings
from multiseek.logic import ReportType

# Re-export author fields
from .author_fields import (
    DyscyplinaQueryObject,
    ForeignKeyDescribeMixin,
    NazwiskoIImie1do3,
    NazwiskoIImie1do5,
    NazwiskoIImieQueryObject,
    NazwiskoIImieWZakresieKolejnosci,
    OstatnieNazwiskoIImie,
    OswiadczenieKENQueryObject,
    PierwszeNazwiskoIImie,
    SlowaKluczoweQueryObject,
    TypOgolnyAutorQueryObject,
    TypOgolnyRecenzentQueryObject,
    TypOgolnyRedaktorQueryObject,
    TypOgolnyTlumaczQueryObject,
)

# Re-export boolean fields
from .boolean_fields import (
    AfiliujeQueryObject,
    BazaSCOPUS,
    BazaWOS,
    DyscyplinaUstawionaQueryObject,
    KierunekStudiowQueryObject,
    LicencjaOpenAccessUstawionaQueryObject,
    ObcaJednostkaQueryObject,
    PublicDostepDniaQueryObject,
    RecenzowanaQueryObject,
    StronaWWWUstawionaQueryObject,
)

# Re-export constants
from .constants import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    NULL_VALUE,
    UNION,
    UNION_FEMALE,
    UNION_NONE,
    UNION_OPS_ALL,
)

# Re-export date fields
from .date_fields import (
    DataUtworzeniaQueryObject,
    OstatnioZmieniony,
)

# Re-export factory functions
from .factories import (
    create_boolean_query_object,
    create_decimal_query_object,
    create_integer_query_object,
    create_string_query_object,
    create_valuelist_query_object,
)

# Re-export numeric fields
from .numeric_fields import (
    ImpactQueryObject,
    IndexCopernicusQueryObject,
    JezykQueryObject,
    LiczbaAutorowQueryObject,
    LiczbaCytowanQueryObject,
    LiczbaZnakowWydawniczychQueryObject,
    PunktacjaSNIP,
    PunktacjaWewnetrznaEnabledMixin,
    PunktacjaWewnetrznaQueryObject,
    PunktyKBNQueryObject,
    RokQueryObject,
    ZakresLatQueryObject,
)

# Re-export openaccess fields
from .openaccess_fields import (
    NazwaKonferencji,
    OpenaccessCzasPublikacjiQueryObject,
    OpenaccessLicencjaQueryObject,
    OpenaccessWersjaTekstuQueryObject,
    StatusKorektyQueryObject,
    TypKBNQueryObject,
    WydawnictwoNadrzedneQueryObject,
    ZewnetrznaBazaDanychQueryObject,
)

# Re-export publication type fields
from .publication_type_fields import (
    CharakterFormalnyQueryObject,
    CharakterOgolnyQueryObject,
    RodzajKonferenckjiQueryObject,
    Typ_OdpowiedzialnosciQueryObject,
    TypRekorduObject,
)

# Re-export string fields
from .string_fields import (
    AdnotacjeQueryObject,
    DOIQueryObject,
    InformacjeQueryObject,
    ORCIDQueryObject,
    SzczegolyQueryObject,
    TytulPracyQueryObject,
    UwagiQueryObject,
    ZrodloQueryObject,
)

# Re-export unit fields
from .unit_fields import (
    AktualnaJednostkaAutoraQueryObject,
    JednostkaQueryObject,
    PierwszaJednostkaQueryObject,
    PierwszyWydzialQueryObject,
    RodzajJednostkiQueryObject,
    WydzialQueryObject,
)

# Build the multiseek_fields registry
multiseek_fields = [
    TytulPracyQueryObject(),
    NazwiskoIImieQueryObject(),
    JednostkaQueryObject(),
]

if getattr(settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True):
    multiseek_fields += [
        WydzialQueryObject(),
    ]

multiseek_fields += [
    Typ_OdpowiedzialnosciQueryObject(),
    TypOgolnyAutorQueryObject(),
    TypOgolnyRedaktorQueryObject(),
    TypOgolnyTlumaczQueryObject(),
    TypOgolnyRecenzentQueryObject(),
    ZakresLatQueryObject(),
    JezykQueryObject(),
    RokQueryObject(),
    TypRekorduObject(),
    CharakterFormalnyQueryObject(),
    CharakterOgolnyQueryObject(),
    TypKBNQueryObject(),
    ZrodloQueryObject(),
    WydawnictwoNadrzedneQueryObject(),
    PierwszeNazwiskoIImie(),
    PierwszaJednostkaQueryObject(),
]

if getattr(settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True):
    multiseek_fields += [
        PierwszyWydzialQueryObject(),
    ]

multiseek_fields += [
    NazwiskoIImie1do3(),
    NazwiskoIImie1do5(),
    OstatnieNazwiskoIImie(),
    ORCIDQueryObject(),
    ImpactQueryObject(),
    LiczbaCytowanQueryObject(),
    LiczbaAutorowQueryObject(),
    PunktyKBNQueryObject(),
    IndexCopernicusQueryObject(),
    PunktacjaSNIP(),
    PunktacjaWewnetrznaQueryObject(),
    InformacjeQueryObject(),
    SzczegolyQueryObject(),
    UwagiQueryObject(),
    SlowaKluczoweQueryObject(),
    AdnotacjeQueryObject(),
    DataUtworzeniaQueryObject(),
    OstatnioZmieniony(),
    RecenzowanaQueryObject(),
    LiczbaZnakowWydawniczychQueryObject(),
    NazwaKonferencji(),
    RodzajKonferenckjiQueryObject(),
    BazaWOS(),
    BazaSCOPUS(),
    OpenaccessWersjaTekstuQueryObject(),
    OpenaccessLicencjaQueryObject(),
    OpenaccessCzasPublikacjiQueryObject(),
    DyscyplinaQueryObject(),
    ZewnetrznaBazaDanychQueryObject(),
    ObcaJednostkaQueryObject(),
    AfiliujeQueryObject(),
    DyscyplinaUstawionaQueryObject(),
    LicencjaOpenAccessUstawionaQueryObject(),
    PublicDostepDniaQueryObject(),
    StronaWWWUstawionaQueryObject(),
    DOIQueryObject(),
    AktualnaJednostkaAutoraQueryObject(),
    RodzajJednostkiQueryObject(),
    KierunekStudiowQueryObject(),
    OswiadczenieKENQueryObject(),
    StatusKorektyQueryObject(),
]


class PunktacjaWewnetrznaReportType(PunktacjaWewnetrznaEnabledMixin, ReportType):
    pass


__all__ = [
    # Constants
    "NULL_VALUE",
    "UNION",
    "UNION_FEMALE",
    "UNION_NONE",
    "UNION_OPS_ALL",
    "EQUAL_PLUS_SUB_FEMALE",
    "EQUAL_PLUS_SUB_UNION_FEMALE",
    # Factory functions
    "create_string_query_object",
    "create_boolean_query_object",
    "create_integer_query_object",
    "create_decimal_query_object",
    "create_valuelist_query_object",
    # Mixins
    "ForeignKeyDescribeMixin",
    "PunktacjaWewnetrznaEnabledMixin",
    # String fields
    "TytulPracyQueryObject",
    "AdnotacjeQueryObject",
    "DOIQueryObject",
    "InformacjeQueryObject",
    "SzczegolyQueryObject",
    "UwagiQueryObject",
    "ORCIDQueryObject",
    "ZrodloQueryObject",
    # Date fields
    "DataUtworzeniaQueryObject",
    "OstatnioZmieniony",
    # Author fields
    "SlowaKluczoweQueryObject",
    "NazwiskoIImieQueryObject",
    "NazwiskoIImieWZakresieKolejnosci",
    "PierwszeNazwiskoIImie",
    "OstatnieNazwiskoIImie",
    "NazwiskoIImie1do3",
    "NazwiskoIImie1do5",
    "TypOgolnyAutorQueryObject",
    "TypOgolnyRedaktorQueryObject",
    "TypOgolnyTlumaczQueryObject",
    "TypOgolnyRecenzentQueryObject",
    "DyscyplinaQueryObject",
    "OswiadczenieKENQueryObject",
    # Unit fields
    "JednostkaQueryObject",
    "AktualnaJednostkaAutoraQueryObject",
    "PierwszaJednostkaQueryObject",
    "WydzialQueryObject",
    "PierwszyWydzialQueryObject",
    "RodzajJednostkiQueryObject",
    # Publication type fields
    "Typ_OdpowiedzialnosciQueryObject",
    "TypRekorduObject",
    "CharakterOgolnyQueryObject",
    "CharakterFormalnyQueryObject",
    "RodzajKonferenckjiQueryObject",
    # Numeric fields
    "ZakresLatQueryObject",
    "JezykQueryObject",
    "RokQueryObject",
    "ImpactQueryObject",
    "LiczbaCytowanQueryObject",
    "LiczbaAutorowQueryObject",
    "PunktacjaWewnetrznaQueryObject",
    "PunktacjaSNIP",
    "PunktyKBNQueryObject",
    "IndexCopernicusQueryObject",
    "LiczbaZnakowWydawniczychQueryObject",
    # OpenAccess fields
    "WydawnictwoNadrzedneQueryObject",
    "StatusKorektyQueryObject",
    "NazwaKonferencji",
    "ZewnetrznaBazaDanychQueryObject",
    "OpenaccessWersjaTekstuQueryObject",
    "OpenaccessLicencjaQueryObject",
    "OpenaccessCzasPublikacjiQueryObject",
    "TypKBNQueryObject",
    # Boolean fields
    "RecenzowanaQueryObject",
    "BazaWOS",
    "BazaSCOPUS",
    "ObcaJednostkaQueryObject",
    "AfiliujeQueryObject",
    "DyscyplinaUstawionaQueryObject",
    "StronaWWWUstawionaQueryObject",
    "LicencjaOpenAccessUstawionaQueryObject",
    "PublicDostepDniaQueryObject",
    "KierunekStudiowQueryObject",
    # Registry and report types
    "multiseek_fields",
    "PunktacjaWewnetrznaReportType",
]
