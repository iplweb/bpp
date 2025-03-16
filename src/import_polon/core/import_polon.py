import decimal
from decimal import Decimal

from import_common.core import matchuj_autora, matchuj_dyscypline
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

from bpp.models import Autor_Dyscyplina, przebuduj_prace_autora_po_udanej_transakcji


def analyze_file_import_polon(fn, parent_model: ImportPlikuPolon):
    data = read_excel_or_csv_dataframe_guess_encoding(fn)
    # pandas.read_excel(fn, header=0).replace({numpy.nan: None})
    records = data.to_dict("records")
    total = len(records)
    for n_row, row in enumerate(records):
        autor = matchuj_autora(
            imiona=(
                (row.get("IMIE", "") or "") + " " + (row.get("DRUGIE", "") or "")
            ).strip(),
            nazwisko=row.get("NAZWISKO", ""),
            pbn_uid_id=row.get("IDETYFIKATOR_OSOBY_PBN")
            or row.get("IDENTYFIKATOR_OSOBY_PBN"),
            orcid=row.get("ORCID", ""),
            tytul_str=row.get(
                "STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU", None
            ),
        )

        bledy = []
        jest_w_n_xlsx = False

        if (row.get("OSWIADCZENIE_N", "") or "").strip().lower() == "tak":
            jest_w_n_xlsx = True

            dyscyplina_naukowa = row.get("DYSCYPLINA_N")
            subdyscyplina_naukowa = row.get("DYSCYPLINA_N_KOLEJNA")
        elif row.get("OSWIADCZENIE_O_DYSCYPLINACH", "").lower() == "tak":
            dyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_PIERWSZA")
            subdyscyplina_naukowa = row.get("OSWIADCZONA_DYSCYPLINA_DRUGA")
        else:
            bledy.append(
                "Brak oświadczenia o dyscyplinach N, brak oświadczenia o dyscyplinach. "
            )

        # W XLS pozostają takie pola:
        # PODSTAWOWE_MIEJSCE_PRACY
        # WYMIAR_ETATU
        # ZATRUDNIENIE_OD
        # ZATRUDNIENIE_DO
        # DATA_ZLOZENIA_OSWIADCZENIA
        # OSWIADCZENIE_O_DYSCYPLINACH
        # CHARAKTER_PRACY
        # GRUPA_STANOWISK

        if autor is None:
            if parent_model.ukryj_niezmatchowanych_autorow:
                # Nie rejestruj, że autora nie udało się zmatchować
                continue

            bledy.append("Nie udało się dopasować autora")

        dyscyplina_xlsx = matchuj_dyscypline(kod=None, nazwa=dyscyplina_naukowa)
        if dyscyplina_naukowa is not None and dyscyplina_xlsx is None:
            bledy.append(
                "Nie udało się dopasować dyscypliny po stronie BPP do dyscypliny z XLSX"
            )

        subdyscyplina_xlsx = matchuj_dyscypline(kod=None, nazwa=subdyscyplina_naukowa)
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

                        rodzaj_autora = Autor_Dyscyplina.RODZAJE_AUTORA.Z
                        if jest_w_n_xlsx:
                            rodzaj_autora = Autor_Dyscyplina.RODZAJE_AUTORA.N

                        autor.autor_dyscyplina_set.create(
                            rodzaj_autora=rodzaj_autora,
                            rok=parent_model.rok,
                            dyscyplina_naukowa=dyscyplina_xlsx,
                            subdyscyplina_naukowa=subdyscyplina_xlsx,
                            wymiar_etatu=wymiar_etatu,
                            procent_dyscypliny=procent_dyscypliny,
                            procent_subdyscypliny=procent_subdyscypliny,
                        )
                    ops.append("Brak wpisu dla tego roku, utworzono zgodnie z XLSX")
                else:
                    ops.append(
                        "Brak wpisu o dyscyplinie dla autora za dany rok w BPP, brak dyscypliny w XLSX. Nic do roboty. "
                    )
            else:
                if ad.dyscyplina_naukowa != dyscyplina_xlsx:
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
                    if ad.rodzaj_autora != Autor_Dyscyplina.RODZAJE_AUTORA.N:
                        ops.append(
                            f"Zmieniam rodzaj autora na {Autor_Dyscyplina.RODZAJE_AUTORA['N']}"
                        )
                        ad.rodzaj_autora = Autor_Dyscyplina.RODZAJE_AUTORA.N
                        rodzaj_autora_zmieniony = True

                else:
                    # Wg pliku XLSX autor NIE jest w N.
                    # Ustawiamy, że nie-jest-w-N.
                    # Doktorantów NIE ruszamy.
                    if ad.rodzaj_autora == Autor_Dyscyplina.RODZAJE_AUTORA.N:
                        ops.append(
                            f"Zmieniam rodzaj autora na {Autor_Dyscyplina.RODZAJE_AUTORA['N']}"
                        )
                        ad.rodzaj_autora = Autor_Dyscyplina.RODZAJE_AUTORA.Z
                        rodzaj_autora_zmieniony = True

                if ops:
                    if parent_model.zapisz_zmiany_do_bazy:
                        ad.save()

                        if rodzaj_autora_zmieniony:
                            przebuduj_prace_autora_po_udanej_transakcji(
                                autor_id=ad.autor_id, rok=ad.rok
                            )

                if not ops:
                    ops.append("W BPP jest identycznie jak w XLSX")

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
