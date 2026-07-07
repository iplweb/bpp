"""PBN publication importer package.

This package provides backward compatibility - all functions that were previously
in importer.py are re-exported here.
"""

import logging

from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Jednostka, Rekord, Rodzaj_Zrodla
from pbn_api.client import PBNClient
from pbn_api.const import DELETED
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
    przetworz_tytuly,
    ustaw_jezyk_oryginalny,
)

# Re-export publisher handling
from .publishers import (
    importuj_jednego_wydawce,
    importuj_wydawcow,
    sciagnij_i_zapisz_wydawce,
)

# Re-export source handling
from .sources import dopisz_jedno_zrodlo, importuj_zrodla

logger = logging.getLogger(__name__)


def _pomin_niekompletny(pbn_uid_id, powod, obiekt):
    """Loguje pominięcie strukturalnie niekompletnego rekordu PBN i zwraca ``None``.

    PBN potrafi zwrócić rekordy-widma (skasowane/wycofane albo w połowie
    zdenormalizowane) bez pól niezbędnych do materializacji rekordu BPP: bez
    wersji bieżącej, bez ``type`` obiektu, albo ``CHAPTER`` bez wskazania książki
    nadrzędnej (``book``). Takiego rekordu nie da się sensownie zaimportować —
    zamiast wywalać cały import ``KeyError``-em (szum w Rollbarze, jeden rekord
    na jedno wystąpienie) pomijamy go, raportując JAWNIE jako znaną kategorię
    (WARNING, greppable po ``pbn_uid_id``). Batch leci dalej.

    To bramka minimum-viable-record. Świadomie łapie WYŁĄCZNIE braki
    STRUKTURALNE — braki opcjonalne (publisher, mainLanguage, pages) obsługują
    poszczególne importery przez łagodną degradację (rekord i tak wchodzi).
    """
    logger.warning(
        "Pomijam niekompletny rekord PBN %s: %s (klucze obiektu: %s)",
        pbn_uid_id,
        powod,
        sorted(obiekt.keys()) if obiekt else obiekt,
    )
    return None


def importuj_publikacje_po_pbn_uid_id(
    pbn_uid_id,
    client: PBNClient,
    default_jednostka: Jednostka,
    force=False,
    rodzaj_periodyk=None,
    dyscypliny_cache=None,
    inconsistency_callback=None,
    domyslny_jezyk=None,
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
        domyslny_jezyk: Język użyty, gdy PBN nie poda języka publikacji albo
               poda kod nieobecny w słowniku ``Jezyk`` (domyślnie: polski).
    """
    pbn_publication = get_or_download_publication(pbn_uid_id, client)

    assert pbn_publication is not None

    # Praca usunięta po stronie PBN nie może materializować się jako świeży
    # rekord BPP. To choke point dla WSZYSTKICH wejść (batch i import po UID).
    if pbn_publication.status == DELETED:
        return None

    cv = pbn_publication.current_version

    # Bramka minimum-viable-record: bez wersji bieżącej / obiektu nie ma z czego
    # tworzyć rekordu.
    if cv is None or not cv.get("object"):
        return _pomin_niekompletny(
            pbn_uid_id, "brak wersji bieżącej / obiektu w PBN", None
        )

    obiekt = cv["object"]
    typ = obiekt.get("type")
    if not typ:
        # Brak ``type`` (Rollbar #413) — nie wiadomo nawet, jak rekord importować.
        return _pomin_niekompletny(pbn_uid_id, "brak pola 'type' w obiekcie", obiekt)

    match typ:
        case "BOOK" | "EDITED_BOOK":
            ret = importuj_ksiazke(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
                inconsistency_callback=inconsistency_callback,
                domyslny_jezyk=domyslny_jezyk,
            )
        case "CHAPTER":
            pbn_book_id = (obiekt.get("book") or {}).get("id")
            if not pbn_book_id:
                # CHAPTER bez książki nadrzędnej (Rollbar #412) — rozdziału-sieroty
                # nie da się powiązać z wydawnictwem zwartym.
                return _pomin_niekompletny(
                    pbn_uid_id, "CHAPTER bez książki nadrzędnej ('book')", obiekt
                )
            importuj_ksiazke(
                pbn_book_id,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
                inconsistency_callback=inconsistency_callback,
                domyslny_jezyk=domyslny_jezyk,
            )
            ret = importuj_rozdzial(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
                inconsistency_callback=inconsistency_callback,
                domyslny_jezyk=domyslny_jezyk,
            )
        case "ARTICLE":
            ret = importuj_artykul(
                pbn_publication.pk,
                default_jednostka=default_jednostka,
                client=client,
                force=force,
                rodzaj_periodyk=rodzaj_periodyk,
                dyscypliny_cache=dyscypliny_cache,
                inconsistency_callback=inconsistency_callback,
                domyslny_jezyk=domyslny_jezyk,
            )
        case _:
            # Nieobsługiwany, ale OBECNY typ to dryf schematu PBN, nie awaria —
            # pomijamy rekord zamiast wywalać batch NotImplementedError-em.
            return _pomin_niekompletny(
                pbn_uid_id, f"nieobsługiwany type={typ!r}", obiekt
            )

    return ret


def importuj_publikacje_instytucji(
    client: PBNClient, default_jednostka: Jednostka, pbn_uid_id=None
):
    niechciane = list(Rekord.objects.values_list("pbn_uid_id", flat=True))
    chciane = (
        Publication.objects.all().exclude(status=DELETED).exclude(pk__in=niechciane)
    )

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
    "przetworz_tytuly",
    "ustaw_jezyk_oryginalny",
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
