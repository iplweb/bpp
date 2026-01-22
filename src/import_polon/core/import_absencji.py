import sys

import rollbar

from bpp.models import Autor_Absencja
from import_common.core import matchuj_autora
from import_polon.models import ImportPlikuAbsencji, WierszImportuPlikuAbsencji
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding


def _parse_rok_nieobecnosc(value: str) -> tuple[int, int] | None:
    """Parse 'YYYY - DDD' format into (year, days) tuple."""
    if not value:
        return None
    try:
        rok, ile_dni = (int(x) for x in value.split(" - ", 2))
        return rok, ile_dni
    except (ValueError, TypeError, AttributeError):
        return None


def _validate_row(row: dict, autor) -> tuple[list[str], int | None, int | None]:
    """Validate row data and return (errors, rok, ile_dni)."""
    bledy = []
    rok, ile_dni = None, None

    if autor is None:
        bledy.append("Nie udało się dopasować autora")
        return bledy, rok, ile_dni

    rok_nieobecnosc = (row.get("ROK_NIEOBECNOSC", "") or "").strip()
    if not rok_nieobecnosc:
        bledy.append("Pusta wartość w kolumnie 'ROK_NIEOBECNOSC'.")
        return bledy, rok, ile_dni

    parsed = _parse_rok_nieobecnosc(rok_nieobecnosc)
    if parsed is None:
        bledy.append(
            "Wartość w kolumnie 'ROK_NIEOBECNOSC' ma nieprawidłowy format; "
            "oczekiwany: liczba,spacja,myślnik,spacja,liczba. Czyli np. '2017 - 306'. "
        )
    else:
        rok, ile_dni = parsed

    return bledy, rok, ile_dni


def _process_absence_record(autor, rok: int, ile_dni: int, zapisz: bool) -> str:
    """Process absence record - update existing or create new."""
    try:
        aa = Autor_Absencja.objects.get(autor=autor, rok=rok)
        if aa.ile_dni != ile_dni:
            rezultat = f"{aa.ile_dni} -> {ile_dni}"
            aa.ile_dni = ile_dni
            if zapisz:
                aa.save()
        else:
            rezultat = "jest identycznie w bazie jak w XLS"
    except Autor_Absencja.DoesNotExist:
        if zapisz:
            Autor_Absencja.objects.create(autor=autor, rok=rok, ile_dni=ile_dni)
        rezultat = "utworzono nowy wpis absencji"
    return rezultat


def analyze_file_import_absencji(fn, parent_model: ImportPlikuAbsencji):
    try:
        data = read_excel_or_csv_dataframe_guess_encoding(fn)
    except ValueError as e:
        # Handle file format errors gracefully
        error_msg = str(e)
        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={"context": "import_absencji", "error_type": "file_format"},
        )
        WierszImportuPlikuAbsencji.objects.create(
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
            extra_data={"context": "import_absencji", "error_type": "unexpected"},
        )
        WierszImportuPlikuAbsencji.objects.create(
            parent=parent_model,
            dane_z_xls={},
            nr_wiersza=0,
            rezultat=error_msg,
        )
        parent_model.send_notification(error_msg, "error")
        raise

    # pandas.read_excel(fn, header=0).replace({numpy.nan: None})
    records = data.to_dict("records")
    total = len(records)
    for n_row, row in enumerate(records):
        autor = matchuj_autora(
            imiona=(row.get("IMIE", "") or "").strip(),
            nazwisko=(row.get("NAZWISKO", "") or "").strip(),
            orcid=(row.get("ORCID", "") or "").strip(),
        )

        bledy, rok, ile_dni = _validate_row(row, autor)

        if bledy:
            rezultat = ". ".join(bledy)
        else:
            assert rok is not None and ile_dni is not None
            rezultat = _process_absence_record(
                autor, rok, ile_dni, parent_model.zapisz_zmiany_do_bazy
            )

        WierszImportuPlikuAbsencji.objects.create(
            parent=parent_model,
            dane_z_xls=row,
            nr_wiersza=n_row + 1,
            autor=autor,
            rok=rok,
            ile_dni=ile_dni,
            rezultat=rezultat,
        )

        parent_model.send_progress(n_row * 100.0 / total)
