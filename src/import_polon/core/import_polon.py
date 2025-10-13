import decimal
from decimal import Decimal

from ewaluacja_common.models import Rodzaj_Autora
from import_common.core import matchuj_autora, matchuj_dyscypline, normalize_date
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

from bpp.models import (
    Autor_Dyscyplina,
    Uczelnia,
    przebuduj_prace_autora_po_udanej_transakcji,
)


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


def analyze_file_import_polon(fn, parent_model: ImportPlikuPolon):
    try:
        data = read_excel_or_csv_dataframe_guess_encoding(fn)
    except ValueError as e:
        # Handle file format errors gracefully
        error_msg = str(e)
        WierszImportuPlikuPolon.objects.create(
            parent=parent_model,
            dane_z_xls={},
            nr_wiersza=0,
            rezultat=f"Błąd: {error_msg}",
        )
        parent_model.send_notification(error_msg, "error")
        raise ValueError(error_msg)
    except Exception as e:
        # Handle any other unexpected errors
        error_msg = f"Błąd podczas wczytywania pliku: {str(e)}"
        WierszImportuPlikuPolon.objects.create(
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

        orcid = row.get("ORCID", "") or ""
        nazwisko = row.get("NAZWISKO", "")

        # Validate ZATRUDNIENIE field - must start with university name
        zatrudnienie = row.get("ZATRUDNIENIE", "")
        (
            is_valid_employment,
            matched_university,
        ) = validate_zatrudnienie_starts_with_university(zatrudnienie)

        # If ZATRUDNIENIE doesn't start with university name, ignore this record
        if not is_valid_employment:
            WierszImportuPlikuPolon.objects.create(
                parent=parent_model,
                dane_z_xls=row,
                nr_wiersza=n_row + 1,
                autor=None,  # No author match since we're ignoring
                dyscyplina_naukowa=None,
                subdyscyplina_naukowa=None,
                rezultat=(
                    f"REKORD ZIGNOROWANY: Pole 'ZATRUDNIENIE' ('{zatrudnienie}') "
                    f"nie zaczyna się od nazwy żadnej uczelni w systemie."
                ),
            )
            parent_model.send_progress(n_row * 100.0 / total)
            continue  # Skip to next record

        autor = matchuj_autora(
            imiona=(
                (row.get("IMIE", "") or "") + " " + (row.get("DRUGIE", "") or "")
            ).strip(),
            nazwisko=nazwisko,
            pbn_uid_id=row.get("IDETYFIKATOR_OSOBY_PBN")
            or row.get("IDENTYFIKATOR_OSOBY_PBN"),
            orcid=orcid,
            tytul_str=row.get(
                "STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU", None
            ),
        )

        bledy = []
        jest_w_n_xlsx = False
        jest_badawczy_xlsx = False

        dyscyplina_naukowa = None
        subdyscyplina_naukowa = None

        if (row.get("OSWIADCZENIE_N", "") or "").strip().lower() == "tak":
            jest_w_n_xlsx = True
            # brak_oswiadczenia_o_dyscyplinach = False
            dyscyplina_naukowa = row.get("DYSCYPLINA_N")
            subdyscyplina_naukowa = row.get("DYSCYPLINA_N_KOLEJNA")
        elif row.get("OSWIADCZENIE_O_DYSCYPLINACH", "").lower() == "tak":
            # brak_oswiadczenia_o_dyscyplinach = False
            dyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_PIERWSZA")
            subdyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_DRUGA")
        else:
            # brak_oswiadczenia_o_dyscyplinach = True
            pass

        # Określ czy autor jest typu B (badawczy) na podstawie danych zatrudnienia
        grupa_stanowisk = (row.get("GRUPA_STANOWISK", "") or "").strip()
        if (
            grupa_stanowisk.lower() == "pracownik badawczo-dydaktyczny"
            or grupa_stanowisk.lower() == "pracownik badawczo-techniczny"
        ):
            jest_badawczy_xlsx = True

        zatrudnienie_od = normalize_date(row.get("ZATRUDNIENIE_OD"))
        zatrudnienie_do = normalize_date(row.get("ZATRUDNIENIE_DO"))

        # W XLS pozostają takie pola, ktorymi sie jeszcze nie zajalem:
        # PODSTAWOWE_MIEJSCE_PRACY
        # DATA_ZLOZENIA_OSWIADCZENIA
        # CHARAKTER_PRACY
        # GRUPA_STANOWISK

        if autor is None:
            if parent_model.ukryj_niezmatchowanych_autorow:
                # Nie rejestruj, że autora nie udało się zmatchować
                continue

            bledy.append("Nie udało się dopasować autora")

        dyscyplina_xlsx = None
        if dyscyplina_naukowa:
            dyscyplina_xlsx = matchuj_dyscypline(kod=None, nazwa=dyscyplina_naukowa)
            if dyscyplina_naukowa is not None and dyscyplina_xlsx is None:
                bledy.append(
                    "Nie udało się dopasować dyscypliny po stronie BPP do dyscypliny z XLSX"
                )

        subdyscyplina_xlsx = None
        if subdyscyplina_naukowa:
            subdyscyplina_xlsx = matchuj_dyscypline(
                kod=None, nazwa=subdyscyplina_naukowa
            )
            if subdyscyplina_naukowa is not None and subdyscyplina_xlsx is None:
                bledy.append(
                    "Nie udało się dopasować subdyscypliny po stronie BPP do dyscypliny z XLSX"
                )

        procent_dyscypliny = Decimal("0.00")

        if dyscyplina_xlsx:
            try:
                procent_dyscypliny = Decimal(
                    row["PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA"]
                )
            except (ValueError, TypeError, decimal.InvalidOperation):
                bledy.append(
                    "Nie można skonwertować procentowego udziału dyscypliny do dziesiętnego typu "
                    "danych (decimal.Decimal)"
                )
        procent_subdyscypliny = Decimal("100.00") - procent_dyscypliny
        if procent_subdyscypliny == Decimal("100.00"):
            procent_subdyscypliny = Decimal("0.00")

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

        if bledy:
            rezultat = ". ".join(bledy)

        else:
            #
            # autor NIE jest None
            #
            ops = []

            try:
                ad = autor.autor_dyscyplina_set.get(rok=parent_model.rok)
            except Autor_Dyscyplina.DoesNotExist:
                if dyscyplina_xlsx:
                    if parent_model.zapisz_zmiany_do_bazy:

                        rodzaj_autora_skrot = "Z"
                        if jest_w_n_xlsx:
                            rodzaj_autora_skrot = "N"
                        elif jest_badawczy_xlsx:
                            rodzaj_autora_skrot = "B"

                        autor.autor_dyscyplina_set.create(
                            rodzaj_autora=Rodzaj_Autora.objects.get(
                                skrot=rodzaj_autora_skrot
                            ),
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
                    ops.append(
                        "W BPP jest identycznie jak w XLSX (brak danych o dyscyplinach)."
                    )

            else:
                if dyscyplina_xlsx is None and subdyscyplina_xlsx is None:
                    # Complete deletion when XLS has no disciplines
                    ops.append(
                        "Usuwam wpis dyscypliny dla autora (brak dyscyplin w XLS)"
                    )
                    if parent_model.zapisz_zmiany_do_bazy:
                        ad.delete()
                        przebuduj_prace_autora_po_udanej_transakcji(
                            autor_id=ad.autor_id, rok=ad.rok
                        )
                    # Skip further processing since entry is deleted
                    continue
                elif ad.dyscyplina_naukowa != dyscyplina_xlsx:
                    if dyscyplina_xlsx is None:
                        ops.append(
                            "POTENCJALNY PROBLEM. Autor ma w systemie przypisaną dyscyplinę {ad.dyscyplina_naukowa}, "
                            "wg pliku XLS miałbym ją usunąć. Proszę zweryfikować manualnie. "
                        )
                    else:
                        ops.append(
                            f"Zmieniam dyscyplinę z {ad.dyscyplina_naukowa} na {dyscyplina_xlsx}"
                        )
                        ad.dyscyplina_naukowa = dyscyplina_xlsx

                if ad.subdyscyplina_naukowa != subdyscyplina_xlsx:
                    ops.append(
                        f"Zmieniam subdyscyplinę z {ad.subdyscyplina_naukowa} na {subdyscyplina_xlsx}"
                    )
                    ad.subdyscyplina_naukowa = subdyscyplina_xlsx

                if ad.procent_dyscypliny != procent_dyscypliny:
                    ops.append(
                        f"Zmieniam procent dyscypliny z {ad.procent_dyscypliny} na {procent_dyscypliny}"
                    )
                    ad.procent_dyscypliny = procent_dyscypliny

                if ad.procent_subdyscypliny != procent_subdyscypliny:
                    ops.append(
                        f"Zmieniam procent dyscypliny z {ad.procent_subdyscypliny} na {procent_subdyscypliny}"
                    )
                    ad.procent_subdyscypliny = procent_subdyscypliny

                if ad.wymiar_etatu != wymiar_etatu:
                    ops.append(
                        f"Zmieniam wymiar etatu z {ad.wymiar_etatu} na {wymiar_etatu}"
                    )
                    ad.wymiar_etatu = wymiar_etatu

                rodzaj_autora_zmieniony = False

                if jest_w_n_xlsx:
                    # Wg pliku XLSX autor jest w N.
                    # Jeżeli w systemie autor nie-jest-w-N, to nalezy ustawić, że jest-w-N
                    # Doktorant zostanie "promowany" do liczby N.
                    if ad.rodzaj_autora.skrot != "N":
                        ops.append(
                            f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot="N")}"
                        )
                        ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="N")
                        rodzaj_autora_zmieniony = True

                else:
                    # Wg pliku XLSX autor NIE jest w N.
                    # Ustawiamy, że nie-jest-w-N.
                    # Doktorantów NIE ruszamy.
                    if ad.rodzaj_autora.skrot == "N":
                        ops.append(
                            f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot="Z")}"
                        )
                        ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="Z")
                        rodzaj_autora_zmieniony = True
                    elif jest_badawczy_xlsx and ad.rodzaj_autora.skrot == "Z":
                        ops.append(
                            f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot="B")}"
                        )
                        ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="B")
                        rodzaj_autora_zmieniony = True
                    elif not jest_badawczy_xlsx and ad.rodzaj_autora.skrot == "B":
                        ops.append(
                            f"Zmieniam rodzaj autora na {Rodzaj_Autora.objects.get(skrot="Z")}"
                        )
                        ad.rodzaj_autora = Rodzaj_Autora.objects.get(skrot="Z")
                        rodzaj_autora_zmieniony = True

                if ops:
                    if parent_model.zapisz_zmiany_do_bazy:
                        ad.zatrudnienie_od = zatrudnienie_od
                        ad.zatrudnienie_do = zatrudnienie_do

                        ad.save()

                        if rodzaj_autora_zmieniony:
                            przebuduj_prace_autora_po_udanej_transakcji(
                                autor_id=ad.autor_id, rok=ad.rok
                            )

                if not ops:
                    ops.append("W BPP jest identycznie jak w XLSX")

            if autor.orcid is None and orcid:
                autor.orcid = orcid
                ops.append("Ustawiam ORCID. ")
                if parent_model.zapisz_zmiany_do_bazy:
                    autor.save()

            rezultat = ", ".join(ops)

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
