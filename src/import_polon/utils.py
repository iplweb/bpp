import os.path
import sys

import numpy as np
import pandas as pd
import rollbar

# Znak wstawiany w miejsce wyciętego środka nazwy pliku.
WIELOKROPEK = "…"


def skroc_nazwe_pliku(sciezka, limit=36):
    """Skraca nazwę pliku do wyświetlenia w tabeli, wycinając ŚRODEK.

    Eksporty z POLON-u nazywają się np. ``rozszerzone_zestawienie_pracownikow_
    podmiotu_na_dzien_wygenerowania_raportu_2026-01-15.xlsx`` — 90 znaków, z
    czego odróżnia je wyłącznie data na końcu. Obcięcie od końca (``truncatechars``,
    ``text-overflow: ellipsis``) zjadłoby właśnie tę datę, więc wycinamy środek
    i zachowujemy oba końce.

    Katalog gubimy przez ``basename``, a nie przez usunięcie zahardkodowanego
    ``protected/import_polon/`` — dzięki temu funkcja przeżyje zmianę
    ``upload_to`` w modelu.

    Zwraca pusty napis dla pustej ścieżki (``FileField`` bez pliku).
    """
    if not sciezka:
        return ""

    nazwa = os.path.basename(str(sciezka))
    if len(nazwa) <= limit:
        return nazwa

    # Budżet znaków po odjęciu wielokropka, dzielony między początek i koniec.
    # Reszta z dzielenia idzie do początku — koniec ma zmieścić datę i
    # rozszerzenie, więc lepiej mu dać stabilną, przewidywalną długość.
    budzet = max(limit - len(WIELOKROPEK), 0)
    dlugosc_ogona = budzet // 2
    dlugosc_glowy = budzet - dlugosc_ogona

    # ``nazwa[-0:]`` zwraca CAŁY napis, nie pusty — bez tego warunku skracanie
    # do bardzo małego limitu dawało wynik DŁUŻSZY od wejścia.
    ogon = nazwa[len(nazwa) - dlugosc_ogona :] if dlugosc_ogona else ""

    return f"{nazwa[:dlugosc_glowy]}{WIELOKROPEK}{ogon}"


def read_excel_or_csv_dataframe_guess_encoding(fn, header=0, nrows=None):
    fn = str(fn)
    fnl = fn.lower().strip()

    if fnl.endswith(".xlsx") or fnl.endswith(".xls"):
        from import_common.util import sprawdz_bombe_dekompresji

        # XLSX to ZIP — odrzuć bombę dekompresyjną przed wczytaniem do pandas.
        sprawdz_bombe_dekompresji(fn)
        try:
            return pd.read_excel(fn, header=0, nrows=nrows).replace({np.nan: None})
        except ValueError as e:
            if "Excel file format cannot be determined" in str(e):
                rollbar.report_exc_info(
                    sys.exc_info(),
                    extra_data={"context": "read_excel_or_csv", "file": fn},
                )
                raise ValueError(
                    "Plik nie jest rozpoznawany jako prawidłowy plik Excel. "
                    "Proszę sprawdzić, czy plik ma właściwy format .xlsx lub .xls "
                    "i czy nie jest uszkodzony."
                ) from e
            raise
        except Exception as e:
            if "not supported" in str(e).lower():
                rollbar.report_exc_info(
                    sys.exc_info(),
                    extra_data={"context": "read_excel_or_csv", "file": fn},
                )
                raise ValueError(
                    "Format pliku nie jest obsługiwany. Proszę użyć pliku Excel (.xlsx, .xls) lub CSV."
                ) from e
            raise
    elif fnl.endswith(".csv"):
        try:
            # Chardet średnio wykrywa właściwą stronę kodową dla eksportów z POLON w CSV...
            return pd.read_csv(
                fn, header=0, sep=";", encoding="windows-1250", nrows=nrows
            ).replace({np.nan: None})
        except (UnicodeEncodeError, UnicodeDecodeError):
            # ale jezeli to nie windows-1250 to niech wykryje:
            import chardet

            # For encoding detection, we need to read some bytes. Use a small sample for efficiency.
            with open(fn, "rb") as f:
                # Read a small sample for encoding detection (first few KB should be enough)
                sample = f.read(8192)
                encoding = chardet.detect(sample)

            return pd.read_csv(
                fn, header=0, sep=";", encoding=encoding["encoding"], nrows=nrows
            ).replace({np.nan: None})

    else:
        file_extension = fn.split(".")[-1] if "." in fn else "brak rozszerzenia"
        raise ValueError(
            f"Niewłaściwy format pliku (rozszerzenie: .{file_extension}). "
            f"Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
        )
