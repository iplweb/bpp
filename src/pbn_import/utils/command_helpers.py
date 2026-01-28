"""Wspólne funkcje pomocnicze dla poleceń PBN import.

Ten moduł zawiera funkcje współdzielone przez polecenia:
- pbn_importuj_uid.py
- fix_missing_imported_pubs.py
"""

import traceback

from django.core.management import CommandError

from bpp.models import Jednostka, Uczelnia
from pbn_api.exceptions import HttpException
from pbn_import.utils.institution_import import znajdz_lub_utworz_jednostke_domyslna
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.utils.statements import (
    importuj_oswiadczenia_pojedynczej_publikacji,
)


def get_validated_default_jednostka(jednostka_name=None, uczelnia=None):
    """Pobierz i zwaliduj domyślną jednostkę.

    Ujednolicona logika dla poleceń importu PBN. Jeśli podano nazwę jednostki,
    próbuje ją znaleźć. W przeciwnym razie tworzy lub znajduje domyślną jednostkę
    dla uczelni.

    Args:
        jednostka_name: Opcjonalna nazwa jednostki do wyszukania.
        uczelnia: Opcjonalna uczelnia. Jeśli nie podano, pobierana jest domyślna.

    Returns:
        Jednostka: Znaleziona lub utworzona jednostka.

    Raises:
        CommandError: Gdy brak domyślnej uczelni lub podana jednostka nie istnieje.
    """
    if uczelnia is None:
        uczelnia = Uczelnia.objects.get_default()

    if uczelnia is None:
        raise CommandError("Brak domyślnej uczelni w systemie")

    if jednostka_name:
        try:
            return Jednostka.objects.get(nazwa=jednostka_name)
        except Jednostka.DoesNotExist:
            raise CommandError(f"Jednostka '{jednostka_name}' nie istnieje") from None
    else:
        default_jednostka, _ = znajdz_lub_utworz_jednostke_domyslna(uczelnia)
        return default_jednostka


def import_publication_with_statements(
    pbn_uid,
    client,
    default_jednostka,
    force=False,
    with_statements=True,
    rodzaj_periodyk=None,
    dyscypliny_cache=None,
    inconsistency_callback=None,
):
    """Import pojedynczej publikacji wraz z oświadczeniami.

    Wrapper łączący import publikacji z pbn_integrator.importer
    i opcjonalny import oświadczeń.

    Args:
        pbn_uid: Identyfikator publikacji w PBN.
        client: Klient PBN API.
        default_jednostka: Domyślna jednostka dla nowych autorów.
        force: Wymuś reimport nawet jeśli publikacja istnieje.
        with_statements: Czy importować również oświadczenia (domyślnie True).
        rodzaj_periodyk: Opcjonalny Rodzaj_Zrodla dla periodyków.
        dyscypliny_cache: Opcjonalny cache dyscyplin naukowych.
        inconsistency_callback: Opcjonalny callback do raportowania niespójności.

    Returns:
        Tuple (result, error_info, statement_counts):
            - result: Zaimportowana publikacja lub None
            - error_info: Dict z kluczami 'message' i 'traceback' lub None
            - statement_counts: Tuple (pobrano, zintegrowano) lub None
    """
    result = None
    error_info = None
    statement_counts = None

    try:
        result = importuj_publikacje_po_pbn_uid_id(
            pbn_uid,
            client=client,
            default_jednostka=default_jednostka,
            force=force,
            rodzaj_periodyk=rodzaj_periodyk,
            dyscypliny_cache=dyscypliny_cache,
            inconsistency_callback=inconsistency_callback,
        )

        if result is not None and with_statements:
            try:
                statement_counts = importuj_oswiadczenia_pojedynczej_publikacji(
                    client,
                    pbn_uid,
                    default_jednostka=default_jednostka,
                    inconsistency_callback=inconsistency_callback,
                )
            except HttpException as e:
                # Oświadczenia mogą nie być dostępne - to nie jest błąd krytyczny
                error_info = {
                    "message": f"Publikacja OK, błąd oświadczeń: HTTP {e.status_code}",
                    "traceback": None,
                }

    except HttpException as e:
        error_info = {
            "message": f"HTTP {e.status_code}: {e.content[:200]}",
            "traceback": traceback.format_exc(),
        }
    except Exception as e:
        error_info = {
            "message": str(e),
            "traceback": traceback.format_exc(),
        }

    return result, error_info, statement_counts
