import pytest
from django.template import Context, Template
from model_bakery import baker

from bpp.models import Autor, Typ_Odpowiedzialnosci, Wydawnictwo_Ciagle
from bpp.models.system import Jezyk
from bpp.templatetags.prace import strip_at_end, znak_na_koncu
from bpp.tests.helpers import autor_ciaglego
from bpp.tests.util import any_doktorat, any_jednostka


@pytest.fixture
def templatetags_data(db):
    """Fixture tworzący dane testowe dla testów templatetags."""
    j = any_jednostka()

    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", tytul=None, slug="A")
    a2 = baker.make(Autor, nazwisko="Nowak", imiona="Jan", tytul=None, slug="B")
    a3 = baker.make(Autor, nazwisko="Nowak", imiona="Jan", tytul=None, slug="C")

    jezyk = baker.make(Jezyk)
    c = baker.make(
        Wydawnictwo_Ciagle,
        tytul="foo",
        tytul_oryginalny="bar",
        uwagi="fo",
        jezyk=jezyk,
    )
    t, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    _ign, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="red.", nazwa="redaktor"
    )
    autor_ciaglego(
        a1, j, c, zapisany_jako="Jan Budnik", typ_odpowiedzialnosci=t, kolejnosc=1
    )
    autor_ciaglego(
        a2,
        j,
        c,
        zapisany_jako="Stefan Kolbe",
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="red."),
        kolejnosc=2,
    )
    autor_ciaglego(
        a3,
        j,
        c,
        zapisany_jako="Testowy Autor",
        kolejnosc=-1,
        typ_odpowiedzialnosci=t,
    )

    doktorat = any_doktorat(tytul_oryginalny="wtf", tytul="lol", autor=a1, jezyk=jezyk)

    return {
        "a1": a1,
        "a2": a2,
        "a3": a3,
        "ciagle": c,
        "doktorat": doktorat,
    }


def test_autorzy(templatetags_data):
    ciagle = templatetags_data["ciagle"]
    assert (
        "[aut.] Testowy Autor, Jan Budnik, [red.] Stefan Kolbe.".upper()
        in ciagle.opis_bibliograficzny()
    )


def test_autorzy_doktorat(templatetags_data):
    doktorat = templatetags_data["doktorat"]
    assert "[AUT.] KOWALSKI JAN." in doktorat.opis_bibliograficzny()


def test_autorzy_z_linkami_tekst_przed_po(templatetags_data):
    ciagle = templatetags_data["ciagle"]
    ciagle.tekst_przed_pierwszym_autorem = "PRZED"
    ciagle.tekst_po_ostatnim_autorze = "PO"

    assert (
        'PRZED [AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, '
        '<a href="/bpp/autor/A/">Jan Budnik</a>, '
        '[RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>PO.'
        in ciagle.opis_bibliograficzny(links="normal")
    )


def test_autorzy_z_linkami(templatetags_data):
    ciagle = templatetags_data["ciagle"]
    a1 = templatetags_data["a1"]
    a2 = templatetags_data["a2"]
    a3 = templatetags_data["a3"]
    doktorat = templatetags_data["doktorat"]

    assert (
        '[AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, '
        '<a href="/bpp/autor/A/">Jan Budnik</a>, '
        '[RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>.'
        in ciagle.opis_bibliograficzny(links="normal")
    )

    assert (
        f'[AUT.] <a href="/admin/bpp/autor/{a3.pk}/change/">Testowy Autor</a>, '
        f'<a href="/admin/bpp/autor/{a1.pk}/change/">Jan Budnik</a>, '
        f'[RED.] <a href="/admin/bpp/autor/{a2.pk}/change/">Stefan Kolbe</a>.'
        in ciagle.opis_bibliograficzny(links="admin")
    )

    assert (
        '[AUT.] <a href="/bpp/autor/A/">Kowalski Jan</a>.'
        in doktorat.opis_bibliograficzny(links="normal")
    )

    assert (
        f'[AUT.] <a href="/admin/bpp/autor/{doktorat.autor.pk}/change/">Kowalski Jan</a>.'
        in doktorat.opis_bibliograficzny(links="admin")
    )


def test_strip_at_end():
    assert strip_at_end("foo.,.,.,") == "foo"


def test_znak_na_koncu_alt():
    assert znak_na_koncu("foo.,.,", ".") == "foo."
    assert znak_na_koncu(".,.,", ".") == ""
    assert znak_na_koncu(None, ",.") is None


def test_znak_na_koncu():
    template = """
    {% load prace %}
    {{ ciag_znakow|znak_na_koncu:", " }}
    """

    t = Template(template)
    c = Context({"ciag_znakow": "loll..."})
    ret = t.render(c).strip()
    assert ret == "loll,"


def test_znak_na_poczatku():
    template = """
    {% load prace %}
    {{ ciag_znakow|znak_na_poczatku:"," }}
    """

    t = Template(template)
    c = Context({"ciag_znakow": "loll"})
    ret = t.render(c).strip()
    assert ret == ", loll"


def test_ladne_numery_prac():
    template = """
    {% load prace %}
    {{ arr|ladne_numery_prac }}
    """

    t = Template(template)
    c = Context({"arr": {1, 2, 3, 4, 5, 10, 11, 12, 15, 16, 20, 25, 30, 31, 32, 33}})
    ret = t.render(c).strip()
    assert ret == "1-5, 10-12, 15-16, 20, 25, 30-33"

    c = Context({"arr": {1, 3, 4, 5}})
    ret = t.render(c).strip()
    assert ret == "1, 3-5"
