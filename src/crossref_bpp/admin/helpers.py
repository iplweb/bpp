import math

from crossref_bpp.core import Komparator
from import_common.normalization import normalize_title


def convert_crossref_to_changeform_initial_data(z: dict) -> dict:
    """
    Funkcja, która przerabia słownik CrossRef API na słownik
    początkowych argumentów dla changeform. Używany wewnętrznie przez
    funkcje bpp django-admina, gdzie potrzeba skonwertować pobrany z
    CrossRef słownik do argumentów początkowych.
    """

    title = z.get("title")
    if isinstance(title, list):
        title = ". ".join(title)
    title = normalize_title(title)

    try:
        tytul_kontenera = z.get("container-title")[0]
    except IndexError:
        tytul_kontenera = None

    zrodlo = None
    if tytul_kontenera:
        zrodlo = Komparator.porownaj_container_title(
            tytul_kontenera
        ).rekord_po_stronie_bpp

    if zrodlo is not None:
        zrodlo = zrodlo.pk

    wydawca_txt = ""
    wydawca_idx = Komparator.porownaj_publisher(
        z.get("publisher")
    ).rekord_po_stronie_bpp
    if wydawca_idx is None:
        wydawca_txt = z.get("publisher")

    charakter_formalny_pk = None
    charakter_formalny = Komparator.porownaj_type(z.get("type")).rekord_po_stronie_bpp
    if charakter_formalny is not None:
        charakter_formalny_pk = charakter_formalny.pk

    jezyk_pk = None
    jezyk = Komparator.porownaj_language(z.get("language")).rekord_po_stronie_bpp
    if jezyk is not None:
        jezyk_pk = jezyk.pk

    issn = None
    e_issn = None
    if z.get("issn-type", []):
        for _issn in z.get("issn-type"):
            if _issn.get("type") == "electronic":
                e_issn = _issn.get("value")
            else:
                issn = _issn.get("value")

    isbn = None
    e_isbn = None
    if z.get("isbn-type", []):
        for _isbn in z.get("isbn-type"):
            if _isbn.get("type") == "electronic":
                e_isbn = _isbn.get("value")
            else:
                isbn = _isbn.get("value")

    # Jeżeli nie udało się pobrać ISSN w poprzedniej pętli przy analizie listy issn-type,
    # wobec tego pobierz ISSN z parametru ISSN po stronie crossref-api. ALE ustaw issn
    # jedynie wtedy gdy jest ono INNE niż e_issn (ustawiony w pętli powyżej):
    if issn is None:
        if z.get("ISSN", None):
            try:
                issn = z.get("ISSN")[0]
            except IndexError:
                issn = None

            if issn is not None:
                if issn == e_issn:
                    # Jeżeli ISSN jest RÓWNY e_issn czyli w polu ISSN w CrossRef API
                    # był podany ISSN typu "electronic", to w takim razie nie używaj tej
                    # wartości jako ISSN.
                    issn = None

    if isbn is None:
        if z.get("ISBN", None):
            try:
                isbn = z.get("ISBN")[0]
            except IndexError:
                isbn = None

            if isbn is not None:
                if isbn == e_isbn:
                    isbn = None

    licencja_pk = None
    licencja_ilosc_miesiecy = None
    for _licencja in z.get("license", []):
        licencja = Komparator.porownaj_license(_licencja).rekord_po_stronie_bpp
        if licencja is not None:
            licencja_pk = licencja.pk
            try:
                licencja_ilosc_miesiecy = int(
                    math.ceil(int(_licencja.get("delay-in-days")) / 30)
                )
            except (TypeError, ValueError):
                pass
            break

    rok = z.get("published", {}).get("date-parts", [[""]])[0][0]

    miejsce_i_rok = ""
    if z.get("publisher-location"):
        miejsce_i_rok = z.get("publisher-location") + " " + str(rok)

    ret = {
        "tytul_oryginalny": title,
        "zrodlo": zrodlo,
        "nr_zeszytu": z.get("issue", ""),
        "strony": z.get("page", ""),
        "slowa_kluczowe": ", ".join('"%s"' % x for x in z.get("subject", [])),
        "wydawca": wydawca_idx,
        "wydawca_opis": wydawca_txt,
        "doi": z.get("DOI"),
        "charakter_formalny": charakter_formalny_pk,
        "jezyk": jezyk_pk,
        "adnotacje": "Dodano na podstawie CrossRef API",
        "e_issn": e_issn,
        "e_isbn": e_isbn,
        "isbn": isbn,
        "oznaczenie_wydania": z.get("edition-number"),
        "miejsce_i_rok": miejsce_i_rok,
        "openaccess_licencja": licencja_pk,
        "openaccess_ilosc_miesiecy": licencja_ilosc_miesiecy,
        "issn": issn,
        "www": z.get("resource", {}).get("primary", {}).get("URL", ""),
        "tom": z.get("volume", ""),
        "rok": rok,
    }

    return ret
