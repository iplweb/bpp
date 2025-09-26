import numpy as np
import pandas as pd


def read_excel_or_csv_dataframe_guess_encoding(fn, header=0):
    fn = str(fn)
    fnl = fn.lower().strip()

    if fnl.endswith(".xlsx") or fnl.endswith(".xls"):
        try:
            return pd.read_excel(fn, header=0).replace({np.nan: None})
        except ValueError as e:
            if "Excel file format cannot be determined" in str(e):
                raise ValueError(
                    "Plik nie jest rozpoznawany jako prawidłowy plik Excel. "
                    "Proszę sprawdzić, czy plik ma właściwy format .xlsx lub .xls "
                    "i czy nie jest uszkodzony."
                ) from e
            raise
        except Exception as e:
            if "not supported" in str(e).lower():
                raise ValueError(
                    "Format pliku nie jest obsługiwany. Proszę użyć pliku Excel (.xlsx, .xls) lub CSV."
                ) from e
            raise
    elif fnl.endswith(".csv"):

        try:
            # Chardet średnio wykrywa właściwą stronę kodową dla eksportów z POLON w CSV...
            return pd.read_csv(fn, header=0, sep=";", encoding="windows-1250").replace(
                {np.nan: None}
            )
        except (UnicodeEncodeError, UnicodeDecodeError):
            # ale jezeli to nie windows-1250 to niech wykryje:
            import chardet

            encoding = chardet.detect(open(fn, "rb").read())
            return pd.read_csv(
                fn, header=0, sep=";", encoding=encoding["encoding"]
            ).replace({np.nan: None})

    else:
        file_extension = fn.split(".")[-1] if "." in fn else "brak rozszerzenia"
        raise ValueError(
            f"Niewłaściwy format pliku (rozszerzenie: .{file_extension}). "
            f"Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
        )
