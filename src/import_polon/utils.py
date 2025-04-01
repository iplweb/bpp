import numpy as np
import pandas as pd


def read_excel_or_csv_dataframe_guess_encoding(fn, header=0):
    fn = str(fn)
    fnl = fn.lower().strip()

    if fnl.endswith(".xlsx") or fnl.endswith(".xls"):
        return pd.read_excel(fn, header=0).replace({np.nan: None})
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
        raise ValueError(f"Nieznany format pliku: {fn}")
