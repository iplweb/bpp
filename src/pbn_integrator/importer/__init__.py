"""PBN publication importer package.

This package provides backward compatibility - all functions that were previously
in importer.py are re-exported here.
"""

from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Jednostka, Rekord, Rodzaj_Zrodla
from pbn_api.client import PBNClient
from pbn_api.models import Publication

# Re-export publication import functions
from .articles import importuj_artykul

# Re-export author handling
from .authors import utworz_autorow
from .books import importuj_ksiazke
from .chapters import importuj_rozdzial

# Re-export helpers
from .helpers import (
    assert_dictionary_empty,
    get_or_download_publication,
    importuj_openaccess,
    importuj_streszczenia,
    pbn_keywords_to_slowa_kluczowe,
    pobierz_jezyk,
    pobierz_lub_utworz_zrodlo,
    przetworz_journal_issue,
    przetworz_metadane_konferencji,
    przetworz_slowa_kluczowe,
)

# Re-export publisher handling
from .publishers import (
    importuj_jednego_wydawce,
    importuj_wydawcow,
    sciagnij_i_zapisz_wydawce,
)

# Re-export source handling
from .sources import dopisz_jedno_zrodlo, importuj_zrodla


def importuj_publikacje_po_pbn_uid_id(
    pbn_uid_id,
    client: PBNClient,
    default_jednostka: Jednostka,
    force=False,
    rodzaj_periodyk=None,
    dyscypliny_cache=None,
):
    """Importuje publikację z PBN do BPP.

    Args:
        pbn_uid_id: Identyfikator publikacji w PBN
        client: Klient PBN API
        default_jednostka: Domyślna jednostka dla autorów
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
        rodzaj_periodyk: Optional Rodzaj_Zrodla instance for "periodyk"
        dyscypliny_cache: Optional dict mapping discipline names to objects
    """
    pbn_publication = get_or_download_publication(pbn_uid_id, client)

    assert pbn_publication is not None

    cv = pbn_publication.current_version

    match cv["object"].pop("type"):
        case "BOOK":
            ret = importuj_ksiazke(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
            )
        case "EDITED_BOOK":
            ret = importuj_ksiazke(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
            )
        case "CHAPTER":
            ret = importuj_ksiazke(
                cv["object"]["book"]["id"],
                default_jednostka=default_jednostka,
                client=client,
                force=force,
            )

            ret = importuj_rozdzial(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
            )

        case "ARTICLE":
            ret = importuj_artykul(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
                rodzaj_periodyk=rodzaj_periodyk,
                dyscypliny_cache=dyscypliny_cache,
            )
        case _:
            raise NotImplementedError(f"Nie obsluze {cv['object']['type']}")

    return ret


def importuj_publikacje_instytucji(
    client: PBNClient, default_jednostka: Jednostka, pbn_uid_id=None
):
    niechciane = list(Rekord.objects.values_list("pbn_uid_id", flat=True))
    chciane = Publication.objects.all().exclude(pk__in=niechciane)

    if pbn_uid_id:
        chciane = chciane.filter(pk=pbn_uid_id)

    # Create cache ONCE before loop
    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

    for pbn_publication in tqdm(chciane):
        ret = importuj_publikacje_po_pbn_uid_id(
            pbn_publication.mongoId,
            client=client,
            default_jednostka=default_jednostka,
            rodzaj_periodyk=rodzaj_periodyk,
            dyscypliny_cache=dyscypliny_cache,
        )

        if pbn_uid_id:
            return ret


# For backward compatibility with internal function names
_pobierz_lub_utworz_autora = None  # Removed - use authors module directly
_przetworz_afiliacje = None  # Removed - use authors module directly
_utworz_nowego_wydawce = None  # Removed - use publishers module directly
_aktualizuj_poziomy_wydawcy = None  # Removed - use publishers module directly
_pobierz_lub_utworz_zrodlo = pobierz_lub_utworz_zrodlo
_pobierz_jezyk = pobierz_jezyk
_przetworz_slowa_kluczowe = przetworz_slowa_kluczowe
_przetworz_metadane_konferencji = przetworz_metadane_konferencji
_przetworz_journal_issue = przetworz_journal_issue

__all__ = [
    # Source handling
    "dopisz_jedno_zrodlo",
    "importuj_zrodla",
    # Publisher handling
    "importuj_jednego_wydawce",
    "importuj_wydawcow",
    "sciagnij_i_zapisz_wydawce",
    # Author handling
    "utworz_autorow",
    # Helpers
    "assert_dictionary_empty",
    "get_or_download_publication",
    "importuj_openaccess",
    "importuj_streszczenia",
    "pbn_keywords_to_slowa_kluczowe",
    "pobierz_jezyk",
    "pobierz_lub_utworz_zrodlo",
    "przetworz_journal_issue",
    "przetworz_metadane_konferencji",
    "przetworz_slowa_kluczowe",
    # Publication imports
    "importuj_artykul",
    "importuj_ksiazke",
    "importuj_rozdzial",
    # Main dispatchers
    "importuj_publikacje_po_pbn_uid_id",
    "importuj_publikacje_instytucji",
    # Backward compatibility aliases
    "_pobierz_lub_utworz_zrodlo",
    "_pobierz_jezyk",
    "_przetworz_slowa_kluczowe",
    "_przetworz_metadane_konferencji",
    "_przetworz_journal_issue",
]
