from import_common.core import matchuj_zrodlo
from import_list_ministerialnych.models import ImportListMinisterialnych
from import_list_ministerialnych.util import (
    napraw_literowki_w_bazie,
    wczytaj_plik_importu_dyscyplin_zrodel,
)

from bpp.models import Dyscyplina_Naukowa


def detect_duplicates(data):
    """
    Detect duplicate journals in the Excel data based on ISSN, E-ISSN, and mniswId.

    Returns a dictionary mapping row numbers to duplicate information:
    {
        row_index: {
            'duplicate_of': first_occurrence_row_index,
            'reasons': ['ISSN', 'E-ISSN', 'mniswId']  # which identifiers are duplicated
        }
    }
    """
    duplicates = {}

    # Track first occurrence of each identifier
    issn_map = {}
    e_issn_map = {}
    mnisw_id_map = {}

    for row_index, elem in enumerate(data, 3):  # Start from row 3 as in main function
        issn = elem.get("issn") or elem.get("issn.1")
        e_issn = elem.get("e-issn") or elem.get("e-issn.1")
        mnisw_id = elem.get("Unikatowy Identyfikator Czasopisma") or elem.get(
            " Unikatowy Identyfikator Czasopisma"
        )

        duplicate_reasons = []
        duplicate_of_rows = []

        # Check ISSN duplicate
        if issn and issn.strip():
            issn = issn.strip()
            if issn in issn_map:
                duplicate_reasons.append("ISSN")
                duplicate_of_rows.append(issn_map[issn])
            else:
                issn_map[issn] = row_index

        # Check E-ISSN duplicate
        if e_issn and e_issn.strip():
            e_issn = e_issn.strip()
            if e_issn in e_issn_map:
                duplicate_reasons.append("E-ISSN")
                if e_issn_map[e_issn] not in duplicate_of_rows:
                    duplicate_of_rows.append(e_issn_map[e_issn])
            else:
                e_issn_map[e_issn] = row_index

        # Check mniswId duplicate
        if mnisw_id:
            # Convert to string for consistent comparison
            mnisw_id_str = str(mnisw_id).strip()
            if mnisw_id_str and mnisw_id_str != "None":
                if mnisw_id_str in mnisw_id_map:
                    duplicate_reasons.append("mniswId")
                    if mnisw_id_map[mnisw_id_str] not in duplicate_of_rows:
                        duplicate_of_rows.append(mnisw_id_map[mnisw_id_str])
                else:
                    mnisw_id_map[mnisw_id_str] = row_index

        # If any duplicates found, record them
        if duplicate_reasons:
            # Use the earliest duplicate row as the primary
            duplicates[row_index] = {
                "duplicate_of": min(duplicate_of_rows),
                "reasons": duplicate_reasons,
            }

    return duplicates


def analyze_excel_file_import_list_ministerialnych(
    fn, parent_model: ImportListMinisterialnych
):
    napraw_literowki_w_bazie()

    try:
        data = wczytaj_plik_importu_dyscyplin_zrodel(fn)
    except ValueError as e:
        # Handle the specific error when Excel file format cannot be determined
        if "Excel file format cannot be determined" in str(e):
            error_msg = (
                "Błąd: Niewłaściwy format pliku. "
                "Proszę przesłać plik w formacie Excel (.xlsx lub .xls). "
                "Otrzymany plik nie jest rozpoznawany jako prawidłowy plik Excel."
            )
            parent_model.wierszimportulistyministerialnej_set.create(
                nr_wiersza=0,
                dane_z_xls={},
                rezultat=error_msg,
            )
            parent_model.send_notification(error_msg, "error")
            # Mark the operation as finished with error but don't re-raise
            # This will be handled by the task_perform method
            raise ValueError(error_msg)
        else:
            # Re-raise other ValueErrors
            raise
    except Exception as e:
        # Handle any other unexpected errors during file reading
        error_msg = f"Błąd podczas wczytywania pliku: {str(e)}"
        parent_model.wierszimportulistyministerialnej_set.create(
            nr_wiersza=0,
            dane_z_xls={},
            rezultat=error_msg,
        )
        parent_model.send_notification(error_msg, "error")
        raise

    total = len(data)

    dry_run = not parent_model.zapisz_zmiany_do_bazy
    rok = parent_model.rok

    # Detect duplicates before processing
    duplicates = detect_duplicates(data)

    for nr_wiersza, elem in enumerate(data, 3):
        parent_model.send_progress(nr_wiersza * 100.0 / total)

        tytul_zrodla = elem["Tytul_1"] or elem["Tytul_2"]

        # Extract mniswId from Excel column "Unikatowy Identyfikator Czasopisma"
        mnisw_id = elem.get("Unikatowy Identyfikator Czasopisma") or elem.get(
            " Unikatowy Identyfikator Czasopisma"
        )  # Handle potential space in column name

        zrodlo = matchuj_zrodlo(
            tytul_zrodla,
            # alt_nazwa=elem["Tytuł 2"],
            issn=elem["issn"] or elem["issn.1"],
            e_issn=elem["e-issn"] or elem["e-issn.1"],
            mnisw_id=mnisw_id,
            disable_fuzzy=True,
            disable_skrot=True,
        )

        # Check if this row is a duplicate
        duplicate_info = duplicates.get(nr_wiersza)
        is_duplicate = duplicate_info is not None
        duplicate_of_row = duplicate_info["duplicate_of"] if duplicate_info else None
        duplicate_reasons = duplicate_info["reasons"] if duplicate_info else []

        if zrodlo is None:
            if not parent_model.ignoruj_zrodla_bez_odpowiednika:
                rezultat = "Brak takiego źródła po stronie BPP"
                if is_duplicate:
                    rezultat = (
                        f"DUPLIKAT wiersza {duplicate_of_row} ({', '.join(duplicate_reasons)}). "
                        + rezultat
                    )

                parent_model.wierszimportulistyministerialnej_set.create(
                    nr_wiersza=nr_wiersza,
                    dane_z_xls=elem,
                    rezultat=rezultat,
                    is_duplicate=is_duplicate,
                    duplicate_of_row=duplicate_of_row,
                    duplicate_reason=(
                        ", ".join(duplicate_reasons) if duplicate_reasons else ""
                    ),
                )
            continue

        try:
            punktacja = elem["Punkty"]
        except KeyError:
            punktacja = elem["Punktacja"]

        operacje = []

        if parent_model.importuj_punktacje:

            # Jest źródło. Sprawdźmy, czy ma punkty za dany rok:
            if zrodlo.punktacja_zrodla_set.filter(rok=rok).exists():
                # Istnieje, sprawdźmy, czy różna:
                pz = zrodlo.punktacja_zrodla_set.get(rok=rok)
                if pz.punkty_kbn != punktacja:
                    operacje.append(
                        f"Różna punktacja (BPP: {pz.punkty_kbn}, XLS {punktacja}), ustawiam na XLS. "
                    )
                    pz.punkty_kbn = punktacja
                    if not dry_run:
                        pz.save(update_fields=["punkty_kbn"])
                else:
                    operacje.append("Punktacja identyczna w BPP i w XLS")
            else:
                operacje.append(f"Ustawiam punktację {punktacja}. ")
                if not dry_run:
                    zrodlo.punktacja_zrodla_set.create(
                        rok=parent_model.rok, punkty_kbn=punktacja
                    )

        if parent_model.importuj_dyscypliny:
            # Sprawdź, czy wszystkie dyscypliny zakodowane w pliku XLSX występują w BPP
            dyscypliny_xlsx = set()
            for nazwa_dyscypliny in list(elem.keys())[9:]:
                if elem[nazwa_dyscypliny] == "x":
                    try:
                        dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(
                            nazwa=nazwa_dyscypliny
                        )
                        dyscypliny_xlsx.add(dyscyplina_naukowa.nazwa)
                    except Dyscyplina_Naukowa.DoesNotExist:
                        operacje.append(
                            f"Dyscyplina o nazwie '{nazwa_dyscypliny}' nie występuje w BPP. "
                        )

            # Aktualne dyscypliny:
            dyscypliny_bpp = {
                x.dyscyplina.nazwa for x in zrodlo.dyscyplina_zrodla_set.filter(rok=rok)
            }

            # Roznica:
            trzeba_usunac = dyscypliny_bpp.difference(dyscypliny_xlsx)
            trzeba_dodac = dyscypliny_xlsx.difference(dyscypliny_bpp)

            if not trzeba_dodac and not trzeba_usunac:
                operacje.append("Dyscypliny zgodne w BPP i w XLSX")
            else:
                dyscypliny_dodane = []
                for nazwa_dyscypliny in trzeba_dodac:
                    dyscypliny_dodane.append(nazwa_dyscypliny)
                    if not dry_run:
                        zrodlo.dyscyplina_zrodla_set.create(
                            rok=rok,
                            dyscyplina=Dyscyplina_Naukowa.objects.get(
                                nazwa=nazwa_dyscypliny
                            ),
                        )
                dyscypliny_usuniete = []
                for nazwa_dyscypliny in trzeba_usunac:
                    dyscypliny_usuniete.append(nazwa_dyscypliny)
                    if not dry_run:
                        zrodlo.dyscyplina_zrodla_set.get(
                            rok=rok,
                            dyscyplina=Dyscyplina_Naukowa.objects.get(
                                nazwa=nazwa_dyscypliny
                            ),
                        ).delete()

                if dyscypliny_dodane:
                    operacje.append(
                        "Dyscypliny dodane: " + ", ".join(dyscypliny_dodane) + ". "
                    )

                if dyscypliny_usuniete:
                    operacje.append(
                        "Dyscypliny wykreślone: "
                        + ", ".join(dyscypliny_usuniete)
                        + ". "
                    )

        # Add duplicate information to rezultat if this is a duplicate
        final_rezultat = ". ".join(operacje)
        if is_duplicate:
            duplicate_msg = f"DUPLIKAT wiersza {duplicate_of_row} ({', '.join(duplicate_reasons)}). "
            final_rezultat = duplicate_msg + final_rezultat

        parent_model.wierszimportulistyministerialnej_set.create(
            nr_wiersza=nr_wiersza,
            dane_z_xls=elem,
            zrodlo=zrodlo,
            rezultat=final_rezultat,
            is_duplicate=is_duplicate,
            duplicate_of_row=duplicate_of_row,
            duplicate_reason=", ".join(duplicate_reasons) if duplicate_reasons else "",
        )
