import decimal
import sys
from decimal import Decimal

import rollbar

from bpp.models import (
    Autor_Dyscyplina,
    Uczelnia,
    przebuduj_prace_autora_po_udanej_transakcji,
)
from ewaluacja_common.models import Rodzaj_Autora
from import_common.core import matchuj_autora, matchuj_dyscypline, normalize_date
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding


def _format_none(value, none_text="pustego"):
    """Format value for display, replacing None with Polish text."""
    return none_text if value is None else value


def validate_zatrudnienie_starts_with_university(zatrudnienie_value):
    """
    Check if ZATRUDNIENIE field starts with any university name from the system.
    Returns (is_valid, university_name) tuple.
    """
    if not zatrudnienie_value or not isinstance(zatrudnienie_value, str):
        return False, None

    zatrudnienie_clean = zatrudnienie_value.strip()

    # Get all university names from the system
    university_names = Uczelnia.objects.values_list("nazwa", flat=True)

    for university_name in university_names:
        if zatrudnienie_clean.startswith(university_name):
            return True, university_name

    return False, None


def _process_disciplines_from_row(row):
    """
    Extract discipline information from XLS row.
    Returns tuple: (dyscyplina_naukowa_name, subdyscyplina_naukowa_name, jest_w_n)
    """
    jest_w_n = False
    dyscyplina_naukowa = None
    subdyscyplina_naukowa = None

    if (row.get("OSWIADCZENIE_N", "") or "").strip().lower() == "tak":
        jest_w_n = True
        dyscyplina_naukowa = row.get("DYSCYPLINA_N")
        subdyscyplina_naukowa = row.get("DYSCYPLINA_N_KOLEJNA")
    elif row.get("OSWIADCZENIE_O_DYSCYPLINACH", "").lower() == "tak":
        dyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_PIERWSZA")
        subdyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_DRUGA")

    return dyscyplina_naukowa, subdyscyplina_naukowa, jest_w_n


def _determine_research_type(row):
    """
    Determine if author is research type (B) based on employment data.
    Returns boolean.
    """
    from import_polon.models import ImportPolonOverride

    grupa_stanowisk = (row.get("GRUPA_STANOWISK", "") or "").strip()

    try:
        override = ImportPolonOverride.objects.get(
            grupa_stanowisk__iexact=grupa_stanowisk
        )
        return override.jest_badawczy
    except ImportPolonOverride.DoesNotExist:
        if grupa_stanowisk.lower() in [
            "pracownik badawczo-dydaktyczny",
            "pracownik badawczo-techniczny",
        ]:
            return True
        return False


def _match_disciplines(dyscyplina_naukowa_name, subdyscyplina_naukowa_name, bledy):
    """
    Match discipline names to database objects.
    Returns tuple: (dyscyplina_xlsx, subdyscyplina_xlsx, updated_bledy)
    """
    dyscyplina_xlsx = None
    if dyscyplina_naukowa_name:
        dyscyplina_xlsx = matchuj_dyscypline(kod=None, nazwa=dyscyplina_naukowa_name)
        if dyscyplina_naukowa_name is not None and dyscyplina_xlsx is None:
            bledy.append(
                "Nie udało się dopasować dyscypliny po stronie BPP do dyscypliny z XLSX"
            )

    subdyscyplina_xlsx = None
    if subdyscyplina_naukowa_name:
        subdyscyplina_xlsx = matchuj_dyscypline(
            kod=None, nazwa=subdyscyplina_naukowa_name
        )
        if subdyscyplina_naukowa_name is not None and subdyscyplina_xlsx is None:
            bledy.append(
                "Nie udało się dopasować subdyscypliny po stronie BPP do dyscypliny z XLSX"
            )

    return dyscyplina_xlsx, subdyscyplina_xlsx


def _calculate_discipline_percentages(row, dyscyplina_xlsx, bledy):
    """
    Calculate discipline percentage splits.
    Returns tuple: (procent_dyscypliny, procent_subdyscypliny, updated_bledy)
    """
    procent_dyscypliny = Decimal("0.00")

    if dyscyplina_xlsx:
        try:
            procent_dyscypliny = Decimal(row["PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA"])
        except (ValueError, TypeError, decimal.InvalidOperation):
            bledy.append(
                "Nie można skonwertować procentowego udziału dyscypliny do dziesiętnego typu "
                "danych (decimal.Decimal)"
            )

    procent_subdyscypliny = Decimal("100.00") - procent_dyscypliny
    if procent_subdyscypliny == Decimal("100.00"):
        procent_subdyscypliny = Decimal("0.00")

    return procent_dyscypliny, procent_subdyscypliny


def _process_wymiar_etatu(row, autor, bledy):
    """
    Process and validate wymiar_etatu (employment fraction).
    Returns tuple: (wymiar_etatu, updated_bledy)
    """
    wymiar_etatu = row.get("WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA")
    if wymiar_etatu is None and autor is not None:
        bledy.append(
            "Pole Wymiar etatu nie może być puste dla zidentyfikowanego autora."
        )

    if wymiar_etatu is not None:
        try:
            wymiar_etatu = Decimal(wymiar_etatu)
        except (TypeError, ValueError, decimal.InvalidOperation):
            try:
                wymiar_etatu = Decimal(wymiar_etatu.replace(",", "."))
            except (TypeError, ValueError, decimal.InvalidOperation):
                if autor is not None:
                    bledy.append(
                        "Brak możliwości skonwertowania wymiaru etatu na liczbę"
                    )

    return wymiar_etatu


def _determine_rodzaj_autora_skrot(jest_w_n_xlsx, jest_badawczy_xlsx):
    """Determine author type code based on XLS flags."""
    if jest_w_n_xlsx:
        return "N"
    if jest_badawczy_xlsx:
        return "B"
    return "Z"


def _create_new_autor_dyscyplina(
    autor,
    parent_model,
    dyscyplina_xlsx,
    subdyscyplina_xlsx,
    procent_dyscypliny,
    procent_subdyscypliny,
    wymiar_etatu,
    zatrudnienie_od,
    zatrudnienie_do,
    jest_w_n_xlsx,
    jest_badawczy_xlsx,
):
    """Create new Autor_Dyscyplina record."""
    ops = []
    if dyscyplina_xlsx:
        if parent_model.zapisz_zmiany_do_bazy:
            rodzaj_autora_skrot = _determine_rodzaj_autora_skrot(
                jest_w_n_xlsx, jest_badawczy_xlsx
            )
            autor.autor_dyscyplina_set.create(
                rodzaj_autora=Rodzaj_Autora.objects.get(skrot=rodzaj_autora_skrot),
                rok=parent_model.rok,
                dyscyplina_naukowa=dyscyplina_xlsx,
                subdyscyplina_naukowa=subdyscyplina_xlsx,
                wymiar_etatu=wymiar_etatu,
                procent_dyscypliny=procent_dyscypliny,
                procent_subdyscypliny=procent_subdyscypliny,
                zatrudnienie_od=zatrudnienie_od,
                zatrudnienie_do=zatrudnienie_do,
            )
        ops.append("Brak wpisu dla tego roku, utworzono zgodnie z XLSX")
    else:
        ops.append("W BPP jest identycznie jak w XLSX (brak danych o dyscyplinach).")
    return ops


def _update_autor_dyscyplina_fields(
    ad,
    dyscyplina_xlsx,
    subdyscyplina_xlsx,
    procent_dyscypliny,
    procent_subdyscypliny,
    wymiar_etatu,
):
    """Update Autor_Dyscyplina field values. Returns list of operations."""
    ops = []

    if ad.dyscyplina_naukowa != dyscyplina_xlsx:
        if dyscyplina_xlsx is None:
            ops.append(
                f"POTENCJALNY PROBLEM. Autor ma w systemie przypisaną dyscyplinę {ad.dyscyplina_naukowa}, "
                "wg pliku XLS miałbym ją usunąć. Proszę zweryfikować manualnie. "
            )
        else:
            ops.append(
                f"Zmieniam dyscyplinę z {_format_none(ad.dyscyplina_naukowa, 'żadną')} "
                f"na {_format_none(dyscyplina_xlsx, 'żadną')}"
            )
            ad.dyscyplina_naukowa = dyscyplina_xlsx

    if ad.subdyscyplina_naukowa != subdyscyplina_xlsx:
        ops.append(
            f"Zmieniam subdyscyplinę z {_format_none(ad.subdyscyplina_naukowa, 'żadną')} "
            f"na {_format_none(subdyscyplina_xlsx, 'żadną')}"
        )
        ad.subdyscyplina_naukowa = subdyscyplina_xlsx

    if ad.procent_dyscypliny != procent_dyscypliny:
        ops.append(
            f"Zmieniam procent dyscypliny z {_format_none(ad.procent_dyscypliny)} "
            f"na {_format_none(procent_dyscypliny)}"
        )
        ad.procent_dyscypliny = procent_dyscypliny

    if ad.procent_subdyscypliny != procent_subdyscypliny:
        ops.append(
            f"Zmieniam procent subdyscypliny z {_format_none(ad.procent_subdyscypliny)} "
            f"na {_format_none(procent_subdyscypliny)}"
        )
        ad.procent_subdyscypliny = procent_subdyscypliny

    if ad.wymiar_etatu != wymiar_etatu:
        ops.append(
            f"Zmieniam wymiar etatu z {_format_none(ad.wymiar_etatu)} "
            f"na {_format_none(wymiar_etatu)}"
        )
        ad.wymiar_etatu = wymiar_etatu

    return ops


def _update_rodzaj_autora(ad, jest_w_n_xlsx, jest_badawczy_xlsx):
    """Update author type (rodzaj_autora). Returns (ops, rodzaj_autora_zmieniony)."""
    ops = []
    rodzaj_autora_zmieniony = False

    # Obsługa przypadku gdy rodzaj_autora jest None
    if ad.rodzaj_autora is None:
        if jest_w_n_xlsx:
            nowy_rodzaj = "N"
        elif jest_badawczy_xlsx:
            nowy_rodzaj = "B"
        else:
            nowy_rodzaj = "Z"
        ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot=nowy_rodzaj)
        ops.append(f"Ustawiam rodzaj autora na {ad.rodzaj_autora}")
        return ops, True

    if jest_w_n_xlsx:
        if ad.rodzaj_autora.skrot != "N":
            ops.append(
                f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot='N')}"
            )
            ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="N")
            rodzaj_autora_zmieniony = True
    else:
        if ad.rodzaj_autora.skrot == "N":
            ops.append(
                f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot='Z')}"
            )
            ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="Z")
            rodzaj_autora_zmieniony = True
        elif jest_badawczy_xlsx and ad.rodzaj_autora.skrot == "Z":
            ops.append(
                f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot='B')}"
            )
            ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="B")
            rodzaj_autora_zmieniony = True
        elif not jest_badawczy_xlsx and ad.rodzaj_autora.skrot == "B":
            ops.append(
                f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot='Z')}"
            )
            ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="Z")
            rodzaj_autora_zmieniony = True

    return ops, rodzaj_autora_zmieniony


def _sync_autor_dyscyplina(
    autor,
    parent_model,
    dyscyplina_xlsx,
    subdyscyplina_xlsx,
    procent_dyscypliny,
    procent_subdyscypliny,
    wymiar_etatu,
    zatrudnienie_od,
    zatrudnienie_do,
    jest_w_n_xlsx,
    jest_badawczy_xlsx,
):
    """
    Create or update Autor_Dyscyplina record based on XLS data.
    Returns list of operation descriptions.
    """
    try:
        ad = autor.autor_dyscyplina_set.get(rok=parent_model.rok)
    except Autor_Dyscyplina.DoesNotExist:
        return _create_new_autor_dyscyplina(
            autor,
            parent_model,
            dyscyplina_xlsx,
            subdyscyplina_xlsx,
            procent_dyscypliny,
            procent_subdyscypliny,
            wymiar_etatu,
            zatrudnienie_od,
            zatrudnienie_do,
            jest_w_n_xlsx,
            jest_badawczy_xlsx,
        )

    # Record exists - check for deletion
    if dyscyplina_xlsx is None and subdyscyplina_xlsx is None:
        ops = ["Usuwam wpis dyscypliny dla autora (brak dyscyplin w XLS)"]
        if parent_model.zapisz_zmiany_do_bazy:
            ad.delete()
            przebuduj_prace_autora_po_udanej_transakcji(
                autor_id=ad.autor_id, rok=ad.rok
            )
        return ops

    # Update fields
    ops = _update_autor_dyscyplina_fields(
        ad,
        dyscyplina_xlsx,
        subdyscyplina_xlsx,
        procent_dyscypliny,
        procent_subdyscypliny,
        wymiar_etatu,
    )

    # Update author type
    rodzaj_ops, rodzaj_autora_zmieniony = _update_rodzaj_autora(
        ad, jest_w_n_xlsx, jest_badawczy_xlsx
    )
    ops.extend(rodzaj_ops)

    # Save changes if any
    if ops:
        if parent_model.zapisz_zmiany_do_bazy:
            ad.zatrudnienie_od = zatrudnienie_od
            ad.zatrudnienie_do = zatrudnienie_do
            ad.save()

            if rodzaj_autora_zmieniony:
                przebuduj_prace_autora_po_udanej_transakcji(
                    autor_id=ad.autor_id, rok=ad.rok
                )
    else:
        ops.append("W BPP jest identycznie jak w XLSX")

    return ops


def _update_autor_orcid(autor, orcid, parent_model):
    """
    Update author's ORCID if needed.
    Returns list of operation descriptions.
    """
    ops = []
    if autor.orcid is None and orcid:
        autor.orcid = orcid
        ops.append("Ustawiam ORCID. ")
        if parent_model.zapisz_zmiany_do_bazy:
            autor.save()
    return ops


def analyze_file_import_polon(fn, parent_model: ImportPlikuPolon):
    try:
        data = read_excel_or_csv_dataframe_guess_encoding(fn)
    except ValueError as e:
        # Handle file format errors gracefully
        error_msg = str(e)
        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={"context": "import_polon", "error_type": "file_format"},
        )
        WierszImportuPlikuPolon.objects.create(
            parent=parent_model,
            dane_z_xls={},
            nr_wiersza=0,
            rezultat=f"Błąd: {error_msg}",
        )
        parent_model.send_notification(error_msg, "error")
        raise ValueError(error_msg) from e
    except Exception as e:
        # Handle any other unexpected errors
        error_msg = f"Błąd podczas wczytywania pliku: {str(e)}"
        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={"context": "import_polon", "error_type": "unexpected"},
        )
        WierszImportuPlikuPolon.objects.create(
            parent=parent_model,
            dane_z_xls={},
            nr_wiersza=0,
            rezultat=error_msg,
        )
        parent_model.send_notification(error_msg, "error")
        raise

    records = data.to_dict("records")
    total = len(records)
    for n_row, row in enumerate(records):
        # Validate employment - skip if invalid (unless ignored)
        if not parent_model.ignoruj_miejsce_pracy:
            zatrudnienie = row.get("ZATRUDNIENIE", "")
            is_valid_employment, _ = validate_zatrudnienie_starts_with_university(
                zatrudnienie
            )
            if not is_valid_employment:
                WierszImportuPlikuPolon.objects.create(
                    parent=parent_model,
                    dane_z_xls=row,
                    nr_wiersza=n_row + 1,
                    autor=None,
                    dyscyplina_naukowa=None,
                    subdyscyplina_naukowa=None,
                    rezultat=(
                        f"REKORD ZIGNOROWANY: Pole 'ZATRUDNIENIE' ('{zatrudnienie}') "
                        f"nie zaczyna się od nazwy żadnej uczelni w systemie."
                    ),
                )
                parent_model.send_progress(n_row * 100.0 / total)
                continue

        # Match author
        orcid = row.get("ORCID", "") or ""
        autor = matchuj_autora(
            imiona=(
                (row.get("IMIE", "") or "") + " " + (row.get("DRUGIE", "") or "")
            ).strip(),
            nazwisko=row.get("NAZWISKO", ""),
            pbn_uid_id=row.get("IDETYFIKATOR_OSOBY_PBN")
            or row.get("IDENTYFIKATOR_OSOBY_PBN"),
            orcid=orcid,
            tytul_str=row.get(
                "STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU", None
            ),
        )

        # Skip unmatched authors if configured
        if autor is None and parent_model.ukryj_niezmatchowanych_autorow:
            continue

        # Process disciplines
        bledy = []
        dyscyplina_naukowa_name, subdyscyplina_naukowa_name, jest_w_n_xlsx = (
            _process_disciplines_from_row(row)
        )
        jest_badawczy_xlsx = _determine_research_type(row)

        # Match disciplines to database objects
        dyscyplina_xlsx, subdyscyplina_xlsx = _match_disciplines(
            dyscyplina_naukowa_name, subdyscyplina_naukowa_name, bledy
        )

        # Calculate percentages
        procent_dyscypliny, procent_subdyscypliny = _calculate_discipline_percentages(
            row, dyscyplina_xlsx, bledy
        )

        # Process employment details
        wymiar_etatu = _process_wymiar_etatu(row, autor, bledy)
        zatrudnienie_od = normalize_date(row.get("ZATRUDNIENIE_OD"))
        zatrudnienie_do = normalize_date(row.get("ZATRUDNIENIE_DO"))

        # Handle author not found
        if autor is None:
            bledy.append("Nie udało się dopasować autora")

        # Generate result
        if bledy:
            rezultat = ". ".join(bledy)
        else:
            # Sync author discipline data
            ops = _sync_autor_dyscyplina(
                autor,
                parent_model,
                dyscyplina_xlsx,
                subdyscyplina_xlsx,
                procent_dyscypliny,
                procent_subdyscypliny,
                wymiar_etatu,
                zatrudnienie_od,
                zatrudnienie_do,
                jest_w_n_xlsx,
                jest_badawczy_xlsx,
            )

            # Update ORCID if needed
            orcid_ops = _update_autor_orcid(autor, orcid, parent_model)
            ops.extend(orcid_ops)

            rezultat = ", ".join(ops)

        # Create result record
        WierszImportuPlikuPolon.objects.create(
            parent=parent_model,
            dane_z_xls=row,
            nr_wiersza=n_row + 1,
            autor=autor,
            dyscyplina_naukowa=dyscyplina_xlsx,
            subdyscyplina_naukowa=subdyscyplina_xlsx,
            rezultat=rezultat,
        )

        parent_model.send_progress(n_row * 100.0 / total)
