"""Normalizacja na poziomie zapytań do bazy danych.

Zawiera wyrażenia ORM (Trim/Replace/Lower) używane do porównywania
wartości w bazie z wartościami pochodzącymi z importu, oraz odpowiadające
im funkcje pythonowe normalizujące napis tak samo jak ORM-owy odpowiednik.
"""

import html

import dateutil
from django.db.models import Value
from django.db.models.functions import Lower, Replace, Trim

# Znormalizowany tytuł w bazie danych -- wyrzucony ciąg znaków [online],
# podwójne spacje pozamieniane na pojedyncze, trim całości
normalized_db_title = Trim(
    Replace(
        Replace(Lower("tytul_oryginalny"), Value(" [online]"), Value("")),
        Value("  "),
        Value(" "),
    )
)

# Znormalizowany skrót nazwy źródła -- wyrzucone spacje i kropki, trim,
# zmniejszone znaki
normalized_db_zrodlo_skrot = Trim(
    Replace(
        Replace(
            Replace(Lower("skrot"), Value(" "), Value("")),
            Value("-"),
            Value(""),
        ),
        Value("."),
        Value(""),
    )
)


def normalize_zrodlo_skrot_for_db_lookup(s):
    # html.unescape: CrossRef API zwraca tytuły z encjami HTML (np.
    # "Leuk. &amp; Lymphoma"), a w bazie zapisany jest goły znak
    # ("Leuk. & Lymphoma"). Bez dekodowania encja zaburza podobieństwo
    # trygramowe i dopasowanie źródła znika (FD#321).
    s = html.unescape(s)
    return s.lower().replace(" ", "").strip().replace("-", "").replace(".", "")


def normalize_date(s):
    if s is None:
        return s

    if isinstance(s, str):
        s = s.strip()

        if not s:
            return

        return dateutil.parser.parse(s)

    return s


# Znormalizowany skrot zrodla do wyszukiwania -- wyrzucone wszystko procz kropek
normalized_db_zrodlo_nazwa = Trim(
    Replace(Lower("nazwa"), Value(" "), Value("")),
)


def normalize_zrodlo_nazwa_for_db_lookup(s):
    # html.unescape: CrossRef API zwraca tytuły z encjami HTML (np.
    # "Leukemia &amp; Lymphoma"), a w bazie zapisana jest goła nazwa
    # ("Leukemia & Lymphoma"). Bez dekodowania encja zaburza podobieństwo
    # trygramowe i dopasowanie źródła znika (FD#321).
    s = html.unescape(s)
    return s.lower().replace(" ", "").strip()


normalized_db_isbn = Trim(Replace(Lower("isbn"), Value("-"), Value("")))
