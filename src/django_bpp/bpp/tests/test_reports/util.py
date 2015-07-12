# -*- encoding: utf-8 -*-
from model_mommy import mommy
from bpp.models import Autor, Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte, \
    Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor, \
    Autor_Jednostka, Funkcja_Autora
from bpp.tests.util import any_autor


USUAL_FIXTURES = [
    'charakter_formalny.json',
    'jezyk.json',
    'um_lublin_uczelnia.json',
    'um_lublin_wydzial.json',
    'typ_kbn.json',
    'typ_odpowiedzialnosci.json',
    'tytul.json',
    'rodzaj_zrodla.json']


def enrich_kw_for_wydawnictwo(_kw):
    for attr in ['tytul_oryginalny', 'tytul', 'uwagi']:
        if attr not in _kw:
            _kw[attr] = attr.replace("_", " ").title()
    return _kw


def autor(jednostka, **kw):
    a = any_autor()
    Autor_Jednostka.objects.create(autor=a, jednostka=jednostka,
                                   funkcja=mommy.make(Funkcja_Autora), **kw)
    return a


def __autor_publikacji(autor, jednostka, rekord, klasa,
                       typ_odpowiedzialnosci=None, **kwargs):
    if typ_odpowiedzialnosci is None:
        typ_odpowiedzialnosci = mommy.make(Typ_Odpowiedzialnosci)
    return klasa.objects.create(
        autor=autor, rekord=rekord, jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        **kwargs)


def autor_ciaglego(autor, jednostka, rekord, typ_odpowiedzialnosci=None,
                   **kwargs):
    return __autor_publikacji(autor, jednostka, rekord,
                              Wydawnictwo_Ciagle_Autor, typ_odpowiedzialnosci,
                              **kwargs)


def ciagle(autor, jednostka, **kw):
    enrich_kw_for_wydawnictwo(kw)
    w = mommy.make(Wydawnictwo_Ciagle, **kw)
    autor_ciaglego(autor, jednostka, w,
                   zapisany_jako="%s %s" % (autor.nazwisko, autor.imiona[0]))
    return w


def autor_zwartego(autor, jednostka, rekord, typ_odpowiedzialnosci=None,
                   **kwargs):
    return __autor_publikacji(autor, jednostka, rekord,
                              Wydawnictwo_Zwarte_Autor, typ_odpowiedzialnosci,
                              **kwargs)


from django_dynamic_fixture import G


def zwarte(autor, jednostka, typ_odpowiedzialnosci, **kw):
    enrich_kw_for_wydawnictwo(kw)
    z = mommy.make(Wydawnictwo_Zwarte, **kw)
    autor_zwartego(autor, jednostka, z, typ_odpowiedzialnosci,
                  zapisany_jako="%s %s" % (autor.nazwisko, autor.imiona[0]))
    return z
