from model_bakery import baker

from bpp.models import (
    Autor_Jednostka,
    Charakter_Formalny,
    Funkcja_Autora,
    Jezyk,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Tytul,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zasieg_Zrodla,
)
from bpp.tests.util import any_autor

USUAL_FIXTURES = [
    "charakter_formalny.json",
    "jezyk.json",
    "um_lublin_uczelnia.json",
    "um_lublin_wydzial.json",
    "typ_kbn.json",
    "typ_odpowiedzialnosci.json",
    "tytul.json",
    "rodzaj_zrodla.json",
]


def enrich_kw_for_wydawnictwo(_kw):
    for attr in ["tytul_oryginalny", "tytul", "uwagi"]:
        if attr not in _kw:
            _kw[attr] = attr.replace("_", " ").title()
    return _kw


def autor(jednostka, **kw):
    a = any_autor()
    Autor_Jednostka.objects.create(
        autor=a, jednostka=jednostka, funkcja=baker.make(Funkcja_Autora), **kw
    )
    return a


def __autor_publikacji(
    autor, jednostka, rekord, klasa, typ_odpowiedzialnosci=None, **kwargs
):
    if typ_odpowiedzialnosci is None:
        typ_odpowiedzialnosci = baker.make(Typ_Odpowiedzialnosci)
    return klasa.objects.create(
        autor=autor,
        rekord=rekord,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        **kwargs,
    )


def autor_ciaglego(autor, jednostka, rekord, typ_odpowiedzialnosci=None, **kwargs):
    return __autor_publikacji(
        autor,
        jednostka,
        rekord,
        Wydawnictwo_Ciagle_Autor,
        typ_odpowiedzialnosci,
        **kwargs,
    )


def ciagle(autor, jednostka, **kw):
    enrich_kw_for_wydawnictwo(kw)
    w = baker.make(Wydawnictwo_Ciagle, **kw)
    autor_ciaglego(
        autor, jednostka, w, zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}"
    )
    return w


def autor_zwartego(autor, jednostka, rekord, typ_odpowiedzialnosci=None, **kwargs):
    return __autor_publikacji(
        autor,
        jednostka,
        rekord,
        Wydawnictwo_Zwarte_Autor,
        typ_odpowiedzialnosci,
        **kwargs,
    )


def zwarte(autor, jednostka, typ_odpowiedzialnosci, **kw):
    enrich_kw_for_wydawnictwo(kw)
    z = baker.make(Wydawnictwo_Zwarte, **kw)
    autor_zwartego(
        autor,
        jednostka,
        z,
        typ_odpowiedzialnosci,
        zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}",
    )
    return z


def stworz_obiekty_dla_raportow():
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
