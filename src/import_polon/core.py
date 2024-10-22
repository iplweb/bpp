import numpy
import pandas

from import_common.core import matchuj_autora, matchuj_dyscypline
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon


def analyze_excel_file_import_polon(fn, parent_model: ImportPlikuPolon):
    data = pandas.read_excel(fn, header=0).replace({numpy.nan: None})
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

        dyscyplina_naukowa = row.get("DYSCYPLINA_N")
        subdyscyplina_naukowa = row.get("DYSCYPLINA_N_KOLEJNA")

        # PODSTAWOWE_MIEJSCE_PRACY
        # WYMIAR_ETATU
        # WIELKOSC_ETATU
        # WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA
        # ZATRUDNIENIE_OD
        # ZATRUDNIENIE_DO
        # DATA_ZLOZENIA_OSWIADCZENIA
        # OSWIADCZENIE_O_DYSCYPLINACH
        # OSWIADCZONA_DYSCYPLINA_PIERWSZA
        # OSWIADCZONA_DYSCYPLINA_DRUGA
        #
        # PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA
        #
        # OSWIADCZENIE_N
        # ILOSC_DYSCYPLIN_W_OSWIADCZENIU_N
        # DYSCYPLINA_N
        # DYSCYPLINA_N_KOLEJNA
        #
        # CHARAKTER_PRACY
        # GRUPA_STANOWISK
        #
        # IDETYFIKATOR_OSOBY_PBN
        # ORCID

        if autor is not None:
            WierszImportuPlikuPolon.objects.create(
                parent=parent_model,
                dane_z_xls=row,
                nr_wiersza=n_row,
                autor=autor,
                dyscyplina_naukowa=matchuj_dyscypline(
                    kod=None, nazwa=dyscyplina_naukowa
                ),
                subdyscyplina_naukowa=matchuj_dyscypline(
                    kod=None, nazwa=subdyscyplina_naukowa
                ),
            )

        parent_model.send_progress(n_row * 100.0 / total)
