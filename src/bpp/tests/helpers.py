"""
Helper functions for creating test objects.

These are non-fixture helpers that can be imported directly in tests.
They were originally in src/conftest.py but moved here for proper importing.
"""

from django.test.client import RequestFactory
from model_bakery import baker


class UserRequestFactory(RequestFactory):
    """RequestFactory z automatycznym przypisaniem usera do request."""

    def __init__(self, user, *args, **kw):
        self.user = user
        super().__init__(*args, **kw)

    def get(self, *args, **kw):
        req = super().get(*args, **kw)
        req.user = self.user
        return req

    def post(self, *args, **kw):
        req = super().post(*args, **kw)
        req.user = self.user
        return req


def _enrich_kw_for_wydawnictwo(_kw):
    """Wzbogaca kwargs o domyślne wartości dla tytułów."""
    for attr in ["tytul_oryginalny", "tytul", "uwagi"]:
        if attr not in _kw:
            _kw[attr] = attr.replace("_", " ").title()
    return _kw


def _stworz_obiekty_dla_raportow():
    """
    Funkcja tworząca standardowe obiekty potrzebne do raportów.
    Używana również jako non-fixture helper.
    """
    from bpp.models import (
        Charakter_Formalny,
        Jezyk,
        Typ_KBN,
        Typ_Odpowiedzialnosci,
        Tytul,
        Zasieg_Zrodla,
    )

    Zasieg_Zrodla.objects.get_or_create(nazwa="krajowy")
    Zasieg_Zrodla.objects.get_or_create(nazwa="międzynarodowy")

    Typ_KBN.objects.get_or_create(skrot="000", nazwa="inne")
    Typ_KBN.objects.get_or_create(skrot="PO", nazwa="Praca Oryginalna")
    Typ_KBN.objects.get_or_create(skrot="PNP", nazwa="Publikacja popularnonaukowa")
    Typ_KBN.objects.get_or_create(skrot="CR", nazwa="Opis Przypadku")
    Typ_KBN.objects.get_or_create(skrot="PP", nazwa="Praca Przeglądowa")
    Typ_KBN.objects.get_or_create(
        skrot="PW", nazwa="Praca wieloośrodkowa", wliczaj_do_rankingu=False
    )

    Charakter_Formalny.objects.get_or_create(skrot="AC", nazwa="Artykuł w czasopismie")
    Charakter_Formalny.objects.get_or_create(
        skrot="KSZ", nazwa="Książka w języku obcym"
    )
    Charakter_Formalny.objects.get_or_create(
        skrot="KSP", nazwa="Książka w języku polskim"
    )
    Charakter_Formalny.objects.get_or_create(
        skrot="ZSZ", nazwa="Streszczenie zjazdowe konferencji międzynarodowej"
    )
    Charakter_Formalny.objects.get_or_create(
        skrot="PSZ", nazwa="Polskie streszczenie zjazdowe"
    )
    Charakter_Formalny.objects.get_or_create(skrot="H", nazwa="Praca habilitacyjna")
    Charakter_Formalny.objects.get_or_create(skrot="D", nazwa="Praca doktorska")
    Charakter_Formalny.objects.get_or_create(
        skrot="Supl", nazwa="Publikacja w suplemencie"
    )
    Charakter_Formalny.objects.get_or_create(skrot="L", nazwa="List do redakcji")
    Charakter_Formalny.objects.get_or_create(skrot="PAT", nazwa="Patent")

    Jezyk.objects.get_or_create(skrot="ang.", nazwa="angielski")
    Jezyk.objects.get_or_create(skrot="pol.", nazwa="polski")

    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="red.", nazwa="redaktor")

    Tytul.objects.get_or_create(skrot="dr", nazwa="doktor")


def autor_ciaglego(autor, jednostka, rekord, typ_odpowiedzialnosci=None, **kwargs):
    """Helper: tworzy Wydawnictwo_Ciagle_Autor."""
    from bpp.models import Typ_Odpowiedzialnosci, Wydawnictwo_Ciagle_Autor

    if typ_odpowiedzialnosci is None:
        typ_odpowiedzialnosci = baker.make(Typ_Odpowiedzialnosci)
    return Wydawnictwo_Ciagle_Autor.objects.create(
        autor=autor,
        rekord=rekord,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        **kwargs,
    )


def autor_zwartego(autor, jednostka, rekord, typ_odpowiedzialnosci=None, **kwargs):
    """Helper: tworzy Wydawnictwo_Zwarte_Autor."""
    from bpp.models import Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte_Autor

    if typ_odpowiedzialnosci is None:
        typ_odpowiedzialnosci = baker.make(Typ_Odpowiedzialnosci)
    return Wydawnictwo_Zwarte_Autor.objects.create(
        autor=autor,
        rekord=rekord,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        **kwargs,
    )


def autor_publikacji(jednostka, **kw):
    """Helper: tworzy autora z przypisaniem do jednostki."""
    from bpp.models import Autor_Jednostka, Funkcja_Autora
    from bpp.tests.util import any_autor

    a = any_autor()
    Autor_Jednostka.objects.create(
        autor=a, jednostka=jednostka, funkcja=baker.make(Funkcja_Autora), **kw
    )
    return a


def ciagle_publikacja(autor, jednostka, **kw):
    """Helper: tworzy wydawnictwo ciągłe z autorem."""
    from bpp.models import Wydawnictwo_Ciagle

    _enrich_kw_for_wydawnictwo(kw)
    w = baker.make(Wydawnictwo_Ciagle, **kw)
    autor_ciaglego(
        autor, jednostka, w, zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}"
    )
    return w


def zwarte_publikacja(autor, jednostka, typ_odpowiedzialnosci, **kw):
    """Helper: tworzy wydawnictwo zwarte z autorem."""
    from bpp.models import Wydawnictwo_Zwarte

    _enrich_kw_for_wydawnictwo(kw)
    z = baker.make(Wydawnictwo_Zwarte, **kw)
    autor_zwartego(
        autor,
        jednostka,
        z,
        typ_odpowiedzialnosci,
        zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}",
    )
    return z


# Aliasy dla kompatybilności wstecznej
stworz_obiekty_dla_raportow_func = _stworz_obiekty_dla_raportow
autor = autor_publikacji
ciagle = ciagle_publikacja
zwarte = zwarte_publikacja
