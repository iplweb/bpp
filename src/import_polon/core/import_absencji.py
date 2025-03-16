from import_common.core import matchuj_autora
from import_polon.models import ImportPlikuAbsencji, WierszImportuPlikuAbsencji
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

from bpp.models import Autor_Absencja


def analyze_file_import_absencji(fn, parent_model: ImportPlikuAbsencji):
    data = read_excel_or_csv_dataframe_guess_encoding(fn)
    # pandas.read_excel(fn, header=0).replace({numpy.nan: None})
    records = data.to_dict("records")
    total = len(records)
    for n_row, row in enumerate(records):
        autor = matchuj_autora(
            imiona=(row.get("IMIE", "") or "").strip(),
            nazwisko=(row.get("NAZWISKO", "") or "").strip(),
            orcid=(row.get("ORCID", "") or "").strip(),
        )

        bledy = []
        rok, ile_dni = None, None

        if autor is None:
            bledy.append("Nie udało się dopasować autora")
        else:
            rok_nieobecnosc = row.get("ROK_NIEOBECNOSC", "").strip()

            if not rok_nieobecnosc:
                bledy.append("Pusta wartość w kolumnie 'ROK_NIEOBECNOSC'.")
            else:
                # "2017 - 306"
                try:
                    rok, ile_dni = (int(x) for x in rok_nieobecnosc.split(" - ", 2))
                except (ValueError, TypeError, AttributeError):
                    bledy.append(
                        "Wartość w kolumnie 'ROK_NIEOBECNOSC' ma nieprawidłowy format; oczekiwany: liczba,spacja,"
                        "myślnik,spacja,liczba. Czyli np. '2017 - 306'. "
                    )

        if bledy:
            rezultat = ". ".join(bledy)
        else:
            try:
                aa = Autor_Absencja.objects.get(
                    autor=autor,
                    rok=rok,
                )
                if aa.ile_dni != ile_dni:
                    rezultat = f"{aa.ile_dni} -> {ile_dni}"
                    aa.ile_dni = ile_dni
                    if parent_model.zapisz_zmiany_do_bazy:
                        aa.save()
                else:
                    rezultat = "jest identycznie w bazie jak w XLS"

            except Autor_Absencja.DoesNotExist:
                if parent_model.zapisz_zmiany_do_bazy:
                    aa = Autor_Absencja.objects.create(
                        autor=autor, rok=rok, ile_dni=ile_dni
                    )
                rezultat = "utworzono nowy wpis absencji"

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
