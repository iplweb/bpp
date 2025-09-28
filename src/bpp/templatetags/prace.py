import json

import lxml.etree
import lxml.html
from django.template import Library

from django.utils.safestring import mark_safe

register = Library()


def strip_at_end(ciag, znaki=",."):
    ciag = ciag.strip()
    while ciag:
        if ciag[-1] in znaki:
            ciag = ciag[:-1]
            continue
        break
    return ciag


def strip_at_beginning(ciag, znaki=",."):
    ciag = ciag.strip()
    while ciag:
        if ciag[0] in znaki:
            ciag = ciag[1:]
            continue
        break
    return ciag


def znak_na_koncu(ciag, znak):
    """Wymusza, aby na końcu ciągu znaków był konkretny znak, czyli przecinek
    albo kropka. Wycina wszelkie kropki i przecinki z końca ciągu i stripuje go,
    zwracając
    """
    if ciag is None:
        return

    ciag = strip_at_end(ciag)
    if ciag:
        return ciag + znak
    return ciag


register.filter(znak_na_koncu)


def znak_na_poczatku(ciag, znak):
    """Wymusza, aby na PRZED ciągiem znaków był konkretny znak ORAZ spacja,
    czyli - przykładowo - przecinek albo kropka, jeżeli ciąg jest nie-pusty;
    do tego wycina wszelkie kropki i przecinki z końca i z początku ciągu
    oraz stripuje go.

    Tag używany do uzyskiwania opisu bibliograficznego.
    """
    if ciag is None:
        return ""

    ciag = strip_at_beginning(strip_at_end(ciag))
    if ciag:
        return znak + " " + ciag
    return ciag


register.filter(znak_na_poczatku)


def ladne_numery_prac(arr):
    """Wyświetla ładne numery prac, tzn. tablicę [1, 2, 5, 6, 7, 8, 12]
    przerobi na 1-2, 5-8, 12

    Filtr wykorzystywany do wyświetlania numerków prac w Kronice Uczelni
    """

    # To może być set(), a set() jest nieposortowany
    nu = sorted(arr)

    if not nu:
        return ""

    buf = str(nu[0])
    last_elem = nu[0]
    cont = False

    for elem in nu[1:]:
        if elem == last_elem + 1:
            last_elem = elem
            cont = True
            continue

        if cont:
            buf += "-" + str(last_elem) + ", " + str(elem)
        else:
            buf += ", " + str(elem)

        last_elem = elem
        cont = False

    if cont:
        buf += "-" + str(last_elem)

    return buf


register.filter(ladne_numery_prac)


@register.filter(name="jsonify")
def jsonify(value):
    """Convert a value to JSON string for use in JSON-LD structured data."""
    if value is None:
        return "null"
    # Handle Django model instances by converting them to string
    if hasattr(value, "_meta"):
        value = str(value)
    return json.dumps(value, ensure_ascii=False)


@register.simple_tag
def opis_bibliograficzny_cache(pk):
    from bpp.models.cache import Rekord

    try:
        return mark_safe(Rekord.objects.get(pk=pk).opis_bibliograficzny_cache)
    except Rekord.DoesNotExist:
        pass

    return "(brak danych)"


CLOSE_TAGS_OPENING = "<html><body><foo>"
CLOSE_TAGS_CLOSING = "</foo></body></html>"


@register.filter(name="close_tags")
def close_tags(s):
    if s is None or not s:
        return s
    s = f"{CLOSE_TAGS_OPENING}{s}{CLOSE_TAGS_CLOSING}"
    s = lxml.html.fromstring(s)
    s = lxml.etree.tostring(s, encoding="unicode")
    s = s[len(CLOSE_TAGS_OPENING) : -len(CLOSE_TAGS_CLOSING)]
    return s


@register.simple_tag
def generate_coins(praca, autorzy):
    """Generate COinS (ContextObjects in Spans) metadata for bibliography managers.
    This allows Zotero, Mendeley and other tools to automatically detect and import citations.
    """
    from urllib.parse import quote

    # Build the OpenURL KEV format string
    coins_data = []

    # Context version
    coins_data.append("ctx_ver=Z39.88-2004")

    # Format - determine if it's a book or article
    if hasattr(praca, "charakter_formalny") and praca.charakter_formalny:
        if (
            "książ" in praca.charakter_formalny.nazwa.lower()
            or "book" in praca.charakter_formalny.nazwa.lower()
        ):
            coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:book")
            coins_data.append("rft.genre=book")
        else:
            coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:journal")
            coins_data.append("rft.genre=article")
    else:
        coins_data.append("rft_val_fmt=info:ofi/fmt:kev:mtx:journal")
        coins_data.append("rft.genre=article")

    # Title
    if praca.tytul_oryginalny:
        coins_data.append(f"rft.title={quote(praca.tytul_oryginalny)}")

    # Authors
    if autorzy:
        for autor in autorzy[:5]:  # Limit to first 5 authors for COinS
            if hasattr(autor, "autor"):
                full_name = f"{autor.autor.nazwisko}, {autor.autor.imiona}"
                coins_data.append(f"rft.au={quote(full_name)}")

    # Publication year
    if praca.rok:
        coins_data.append(f"rft.date={praca.rok}")

    # Journal/Source title
    if hasattr(praca, "zrodlo") and praca.zrodlo:
        coins_data.append(f"rft.jtitle={quote(str(praca.zrodlo))}")

    # Volume
    if hasattr(praca, "tom") and praca.tom:
        coins_data.append(f"rft.volume={quote(str(praca.tom))}")

    # Issue
    if hasattr(praca, "numer_zeszytu") and praca.numer_zeszytu:
        coins_data.append(f"rft.issue={quote(str(praca.numer_zeszytu))}")

    # Pages
    if hasattr(praca, "pierwsza_strona") and praca.pierwsza_strona:
        coins_data.append(f"rft.spage={praca.pierwsza_strona}")
    if hasattr(praca, "ostatnia_strona") and praca.ostatnia_strona:
        coins_data.append(f"rft.epage={praca.ostatnia_strona}")

    # Identifiers
    if hasattr(praca, "doi") and praca.doi:
        coins_data.append(f"rft_id=info:doi/{quote(praca.doi)}")
    if hasattr(praca, "isbn") and praca.isbn:
        coins_data.append(f"rft.isbn={quote(praca.isbn)}")
    if hasattr(praca, "issn") and praca.issn:
        coins_data.append(f"rft.issn={quote(praca.issn)}")

    # Publisher
    if hasattr(praca, "wydawca") and praca.wydawca:
        coins_data.append(f"rft.pub={quote(str(praca.wydawca))}")

    # Language
    if hasattr(praca, "jezyk") and praca.jezyk:
        lang = praca.jezyk.skrot if hasattr(praca.jezyk, "skrot") else "pl"
        coins_data.append(f"rft.language={lang}")

    # Join all parts with &
    coins_string = "&".join(coins_data)

    # Return the complete COinS span
    return mark_safe(f'<span class="Z3988" title="{coins_string}"></span>')
