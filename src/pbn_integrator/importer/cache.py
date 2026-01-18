"""Cache module for reference data lookups in PBN importer.

This module provides cached access to frequently-used reference objects
(Charakter_Formalny, Status_Korekty, Typ_KBN) to avoid repeated database
queries during import operations.
"""

from functools import lru_cache


@lru_cache(maxsize=1)
def get_charakter_formalny_artykul():
    """Cache Charakter_Formalny for 'Artykuł w czasopismie'."""
    from bpp.models import Charakter_Formalny

    return Charakter_Formalny.objects.get(nazwa="Artykuł w czasopismie")


@lru_cache(maxsize=1)
def get_charakter_formalny_ksiazka():
    """Cache Charakter_Formalny for 'Książka'."""
    from bpp.models import Charakter_Formalny

    return Charakter_Formalny.objects.get(nazwa="Książka")


@lru_cache(maxsize=1)
def get_charakter_formalny_rozdzial():
    """Cache Charakter_Formalny for 'Rozdział książki'."""
    from bpp.models import Charakter_Formalny

    return Charakter_Formalny.objects.get(nazwa="Rozdział książki")


@lru_cache(maxsize=1)
def get_status_korekty_przed():
    """Cache Status_Korekty for 'przed korektą'."""
    from bpp.models import Status_Korekty

    return Status_Korekty.objects.get(nazwa="przed korektą")


@lru_cache(maxsize=1)
def get_typ_kbn_inne():
    """Cache Typ_KBN for 'inne'."""
    from bpp.models import Typ_KBN

    return Typ_KBN.objects.get(nazwa="inne")


def clear_cache():
    """Clear all cached reference data (useful for testing)."""
    get_charakter_formalny_artykul.cache_clear()
    get_charakter_formalny_ksiazka.cache_clear()
    get_charakter_formalny_rozdzial.cache_clear()
    get_status_korekty_przed.cache_clear()
    get_typ_kbn_inne.cache_clear()
