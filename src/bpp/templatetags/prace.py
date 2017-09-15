# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.template import Library
from django import template
import lxml.html
from django.utils.safestring import mark_safe

register = Library()


class AutorzyNode(template.Node):
    url = None

    def __init__(self, varname):
        self.variable = template.Variable(varname)

    def render(self, context):
        def moj_zapisany(s, slug):
            pre = post = ''
            if self.url:
                pre = '<a href="' + reverse(self.url, args=(slug, )) + '">'
                post = '</a>'
                return pre + s + post
            return s.upper()

        value = self.variable.resolve(context)
        if hasattr(value, 'autorzy'):
            through = value.autorzy.through
            autorzy_tej_pracy = through.objects.filter(rekord=value).order_by('typ_odpowiedzialnosci', 'kolejnosc')

            ret = []
            prev_typ = None
            for autor in autorzy_tej_pracy:
                azj = moj_zapisany(autor.zapisany_jako, autor.autor.slug)
                if prev_typ != autor.typ_odpowiedzialnosci:
                    prev_typ = autor.typ_odpowiedzialnosci
                    ret.append("[%s] %s" % (prev_typ.skrot.upper(), azj))
                    continue
                ret.append(azj)

            retval = ", ".join(ret)

        elif hasattr(value, 'autor'):
            retval = "[AUT.] " + moj_zapisany("%s %s" % (value.autor.nazwisko, value.autor.imiona),
                                value.autor.slug)
        else:
            raise template.TemplateSyntaxError(
                "%r wymaga obiektu z atrybutem autorzy lub autor, dostal %r" % (
                self, value))

        retval = retval.strip()

        if retval.endswith("."):
            return retval

        if retval.endswith(".</a>"):
            retval = retval[:-5] + "</a>"

        return retval + ". "

class AutorzyZLinkamiNode(AutorzyNode):
    url = "bpp:browse_autor"


def __autorzy(parser, token, klass):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, varname = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
    return klass(varname)

autorzy = lambda parser, token: __autorzy(parser, token, AutorzyNode)
autorzy_z_linkami = lambda parser, token: __autorzy(parser, token, AutorzyZLinkamiNode)

register.tag("autorzy", autorzy)
register.tag("autorzy_z_linkami", autorzy_z_linkami)


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
    if type(pk) in [str, str]:
        if pk.find("_") > 0:
            content_type_id, object_id = [int(x) for x in pk.split("_")]
            from bpp.models.cache import Rekord
            return mark_safe(
                Rekord.objects.get(
                    object_id=object_id,
                    content_type_id=content_type_id
                ).opis_bibliograficzny_cache
            )

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

