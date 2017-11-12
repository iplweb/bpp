# -*- encoding: utf-8 -*-
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
        return ''

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
    nu = list(arr)
    nu.sort()

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

@register.simple_tag
def opis_bibliograficzny_cache(pk):
    from bpp.models.cache import Rekord
    try:
        return mark_safe(
            Rekord.objects.get(pk=pk).opis_bibliograficzny_cache
        )
    except Rekord.DoesNotExist:
        pass

    return "(brak danych)"

@register.filter(name='close_tags')
def close_tags(s):
    if s is None or not s:
        return s
    s = "<foo>%s</foo>" % s
    s = lxml.html.fromstring(s)
    s = lxml.etree.tostring(s, encoding="unicode")
    s = s[5:-6]
    return s

