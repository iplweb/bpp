"""Autocomplete views for BPP models.

This module has been split into smaller, focused submodules:
- base.py: Base mixins and helper functions
- search_services.py: Global search functions
- navigation.py: Navigation autocomplete views
- simple.py: Simple autocomplete views for various models
- authors.py: Author-related autocomplete views
- units.py: Jednostka (unit) autocomplete views
- publications.py: Publication-related autocomplete views
- mixins.py: SanitizedAutocompleteMixin
- wydawnictwo_nadrzedne_w_pbn.py: PBN parent publication autocomplete

For backward compatibility, all classes are re-exported from this module.
"""

# Base classes and utilities
# Author autocompletes
from .authors import (  # noqa: F401
    AutorAutocomplete,
    AutorAutocompleteBase,
    AutorZUczelniAutocopmlete,
    Dyscyplina_Naukowa_PrzypisanieAutocomplete,
    PodrzednaPublikacjaHabilitacyjnaAutocomplete,
    PublicAutorAutocomplete,
    ZapisanyJakoAutocomplete,
)
from .base import (  # noqa: F401
    JednostkaMixin,
    NazwaLubSkrotMixin,
    NazwaMixin,
    NazwaTrigramMixin,
    autocomplete_create_error,
)

# Mixins
from .mixins import SanitizedAutocompleteMixin  # noqa: F401

# Navigation autocompletes
from .navigation import (  # noqa: F401
    AdminNavigationAutocomplete,
    DjangoApp,
    DjangoModel,
    GlobalNavigationAutocomplete,
    StaffRequired,
)

# Publication autocompletes
from .publications import (  # noqa: F401
    PublicWydawnictwo_NadrzedneAutocomplete,
    Wydawnictwo_CiagleAdminAutocomplete,
    Wydawnictwo_NadrzedneAutocomplete,
    Wydawnictwo_ZwarteAdminAutocomplete,
)

# Search services
from .search_services import (  # noqa: F401
    AUTOR_ONLY,
    AUTOR_SELECT_RELATED,
    globalne_wyszukiwanie_autora,
    globalne_wyszukiwanie_jednostki,
    globalne_wyszukiwanie_journal,
    globalne_wyszukiwanie_publication,
    globalne_wyszukiwanie_scientist,
    globalne_wyszukiwanie_zrodla,
    jest_czyms,
    jest_orcid,
    jest_pbn_uid,
)

# Simple autocompletes
from .simple import (  # noqa: F401
    Dyscyplina_NaukowaAutocomplete,
    KierunekStudiowAutocomplete,
    KonferencjaAutocomplete,
    LataAutocomplete,
    OrganPrzyznajacyNagrodyAutocomplete,
    PublicKonferencjaAutocomplete,
    PublicStatusKorektyAutocomplete,
    PublicTaggitTagAutocomplete,
    PublicWydzialAutocomplete,
    PublicZrodloAutocomplete,
    PublisherAutocomplete,
    Seria_WydawniczaAutocomplete,
    WydawcaAutocomplete,
    WydzialAutocomplete,
    Zewnetrzna_Baza_DanychAutocomplete,
    ZrodloAutocomplete,
    ZrodloAutocompleteNoCreate,
)

# Unit autocompletes
from .units import (  # noqa: F401
    JednostkaAutocomplete,
    PublicJednostkaAutocomplete,
    WidocznaJednostkaAutocomplete,
)

# PBN parent publication autocomplete
from .wydawnictwo_nadrzedne_w_pbn import (  # noqa: F401
    Wydawnictwo_Nadrzedne_W_PBNAutocomplete,
)
