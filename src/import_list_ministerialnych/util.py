import numpy
import pandas

from bpp.models import Dyscyplina_Naukowa


def napraw_literowki_w_bazie():
    # Usuń zbędne spacje z systemowego słownika dyscyplin BPP,
    # napraw literówki

    for elem in Dyscyplina_Naukowa.objects.all():
        nowa_nazwa = elem.nazwa.strip()
        if nowa_nazwa == "językoznastwo":
            nowa_nazwa = "językoznawstwo"
        if nowa_nazwa == "literaturoznastwo":
            nowa_nazwa = "literaturoznawstwo"
        if elem.nazwa != nowa_nazwa:
            elem.nazwa = nowa_nazwa
            elem.save(update_fields=["nazwa"])


def wczytaj_plik_importu_dyscyplin_zrodel(fn):
    try:
        data = pandas.read_excel(fn, header=1).replace({numpy.nan: None})
    except ValueError as e:
        if "Excel file format cannot be determined" in str(e):
            # Re-raise with a more user-friendly message
            raise ValueError(
                "Plik nie jest rozpoznawany jako prawidłowy plik Excel. "
                "Proszę sprawdzić, czy plik ma rozszerzenie .xlsx lub .xls "
                "i czy nie jest uszkodzony."
            ) from e
        raise
    except Exception as e:
        # Handle other pandas errors
        if "not supported" in str(e).lower():
            raise ValueError(
                "Format pliku nie jest obsługiwany. Proszę użyć pliku Excel (.xlsx lub .xls)."
            ) from e
        raise

    # Problem polega na tym, że numerki w XLSie to nie sa kody dyscyplin. Oczko wyżej są ich
    # nazwy, które zakładam, że są prawidłowe; moglibyśmy wczytać tylko jeden plik ale wówczas
    # musielibysmy skorzystac z multi-indexu. Zatem wczytamy dwa wiersze pliku XLS jeszcze
    # raz i użyjemy ich zeby pozamieniac nazwy z pojedynczego indeksu dataframe'u data

    labels = pandas.read_excel(fn, header=[0, 1], nrows=0)

    # labels.axes[1] zawiera pary tytułów kolumn.
    for nazwa, zly_kod in labels.axes[1][9:]:
        data = data.rename({zly_kod: nazwa}, axis=1, errors="raise")

    try:
        data = data.rename(
            {
                "stosunki międzynaropdowe": "stosunki międzynarodowe",
            },
            axis=1,
            errors="raise",
        )
    except KeyError:
        pass
    try:
        data = data.rename(
            {
                "Tytuł 1": "Tytul_1",
                "Tytuł 2": "Tytul_2",
            },
            axis=1,
            errors="raise",
        )
    except KeyError:
        pass

    # Dane z XLSa będą miały klucze z nazwami dyscyplin czyli np { 'archeologia': 'x' }
    return data.to_dict("records")
