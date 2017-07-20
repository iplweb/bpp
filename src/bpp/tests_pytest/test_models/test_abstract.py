# -*- encoding: utf-8 -*-
import pytest
from lxml.etree import Element
from model_mommy import mommy

from bpp.models.konferencja import Konferencja
from bpp.models.nagroda import Nagroda
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Jednostka, Wydzial
from bpp.models.system import Charakter_PBN, Charakter_Formalny, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor, \
    Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_eksport_pbn_outstanding():
    wz = mommy.make(Wydawnictwo_Zwarte, praca_wybitna=True,
                    uzasadnienie_wybitnosci="foobar")
    toplevel = Element('test')
    wz.eksport_pbn_outstanding(toplevel)
    assert len(toplevel.getchildren()) == 2

    wz.praca_wybitna = False
    toplevel = Element('test')
    wz.eksport_pbn_outstanding(toplevel)
    assert len(toplevel.getchildren()) == 0

@pytest.mark.django_db
def test_eksport_pbn_outstanding():
    wz = mommy.make(Wydawnictwo_Zwarte)

    toplevel = Element('test')
    wz.eksport_pbn_award(toplevel)
    assert len(toplevel.getchildren()) == 0

    n1 = mommy.make(Nagroda,
                   object=wz,
                   rok_przyznania=2000,
                   uzasadnienie="foobar")

    n1 = mommy.make(Nagroda,
                   object=wz,
                   rok_przyznania=2001,
                   uzasadnienie="baz quux")

    toplevel = Element('test')
    wz.eksport_pbn_award(toplevel)
    assert len(toplevel.getchildren()) == 2


@pytest.mark.django_db
def test_eksport_pbn_issn():
    wz = mommy.make(Wydawnictwo_Zwarte, issn="foobar")

    toplevel = Element('test')
    wz.eksport_pbn_issn(toplevel)
    assert len(toplevel.getchildren())

    wz.issn = None
    toplevel = Element('test')
    wz.eksport_pbn_issn(toplevel)
    assert len(toplevel.getchildren()) == 0


@pytest.mark.django_db
def test_eksport_pbn_seria():
    s = mommy.make(Seria_Wydawnicza, nazwa="TEST")
    wz = mommy.make(Wydawnictwo_Zwarte, seria_wydawnicza=s, numer_w_serii="15")

    toplevel = Element('test')
    wz.eksport_pbn_series(toplevel)
    wz.eksport_pbn_number_in_series(toplevel)
    assert len(toplevel.getchildren()) == 2

    wz.seria_wydawnicza = None
    wz.numer_w_serii = None
    wz.save()

    toplevel = Element('test')
    wz.eksport_pbn_series(toplevel)
    wz.eksport_pbn_number_in_series(toplevel)
    assert len(toplevel.getchildren()) == 0

@pytest.mark.django_db
def test_eksport_pbn_conference():
    konf = mommy.make(Konferencja)
    wc = mommy.make(Wydawnictwo_Zwarte, konferencja=konf)
    toplevel = Element('test')
    wc.eksport_pbn_conference(toplevel)
    assert len(toplevel.getchildren())


@pytest.mark.django_db
def test_eksport_pbn_is():
    c_pbn = mommy.make(Charakter_PBN, identyfikator='fubar')
    c = mommy.make(Charakter_Formalny, charakter_pbn=c_pbn)

    c_pbn2 = mommy.make(Charakter_PBN, identyfikator='baz')
    t = mommy.make(Typ_KBN, charakter_pbn=c_pbn2)

    wz = mommy.make(Wydawnictwo_Zwarte,
                    charakter_formalny=c,
                    typ_kbn=t)

    toplevel = Element('test')
    wz.eksport_pbn_is(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == "fubar"

    c.charakter_pbn = None
    c.save()

    toplevel = Element('test')
    wz.eksport_pbn_is(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == "baz"

    t.charakter_pbn = None
    t.save()

    toplevel = Element('test')
    wz.eksport_pbn_is(toplevel=toplevel)
    with pytest.raises(IndexError):
        assert toplevel.getchildren()[0]


@pytest.mark.parametrize(
    "klass, pbn_id,expected",
    [(Wydawnictwo_Ciagle, 500, "500"),
     (Wydawnictwo_Ciagle, None, "2000000100"),
     (Wydawnictwo_Zwarte, None, "4000000100")
     ]
)
@pytest.mark.django_db
def test_eksport_pbn_system_identifier(klass, pbn_id, expected):
    wc = mommy.make(klass, pbn_id=pbn_id, pk=100)
    toplevel = Element('test')
    wc.eksport_pbn_system_identifier(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == expected


@pytest.mark.django_db
def test_eksport_pbn_author_afiliacja_w_kontekscie_wydzialu(uczelnia,
                                                            autor_jan_kowalski, wydawnictwo_zwarte, standard_data):
    w1 = mommy.make(Wydzial, uczelnia=uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=uczelnia)

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=uczelnia)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=uczelnia)

    # Przypisz autora do DWÓCH jednostek z różnych wydziałów
    autor_jan_kowalski.dodaj_jednostke(j1)
    autor_jan_kowalski.dodaj_jednostke(j2)

    # W pracy określ afiliację do drugiego wydziału
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, j2)

    # I teraz:
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_author(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 0

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "1"

    # Zaś dla drugiego wydziału
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_author(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"

@pytest.mark.django_db
def test_eksport_pbn_editor_afiliacja_w_kontekscie_wydzialu(
        uczelnia, autor_jan_kowalski, wydawnictwo_zwarte,
        typy_odpowiedzialnosci):
    w1 = mommy.make(Wydzial, uczelnia=uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=uczelnia)

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=uczelnia)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=uczelnia)

    # Przypisz autora do DWÓCH jednostek z różnych wydziałów
    autor_jan_kowalski.dodaj_jednostke(j1)
    autor_jan_kowalski.dodaj_jednostke(j2)

    # W pracy określ afiliację do drugiego wydziału
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, j2, typ_odpowiedzialnosci_skrot="red.")

    # I teraz:
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 0

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_editors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "1"

    # Zaś dla drugiego wydziału
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_editors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input,expected",
    [
        ("123", "123"),
        ("123 s.", "123"),
        ("123-123", "123-123"),
        ("s. 35", "35"),
        ("ss. 90", "90"),
        ("ss. 190", "190"),
        ("ss. 290", "290"),
        ("s. 10-20", "10-20"),
        ("tia", None),
        ("s. e27-e53", "e27-e53"),
        ("[b.pag.]", "brak"),
        ("[b. pag.]", "brak"),
        ("[b. pag]", "brak"),
        ("s. 132-153.", "132-153"),
        ("s. 143.", "143"),
        ("aosidfjoaisd fjoiasdjf s. 132-153.", "132-153"),
        ("      s. 143.", "143"),
        ("      s.          143.", "143"),
        ("s. P-29.", "P-29"),
        ("s. PP-4.", "PP-4"),
        # ("s. P-27-P-28.", "P-27-P-28"), # to się nie uda
        ("s. xiii-xiv.", "xiii-xiv")
    ])
def test_eksport_pbn_zakres_stron(input, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.szczegoly = input
    ret = wydawnictwo_ciagle.eksport_pbn_zakres_stron()
    assert ret == expected


@pytest.mark.django_db
def test_eksport_pbn_zakres_stron_pole(wydawnictwo_ciagle):
    """Przetestuj że w sytuacji, gdy jest wypełnione pole 'Strony', to
    jego wartość idzie do eksportu"""
    wydawnictwo_ciagle.szczegoly = "s. 35"
    wydawnictwo_ciagle.strony = "44-44"
    ret = wydawnictwo_ciagle.eksport_pbn_zakres_stron()
    assert ret == "44-44"

    wydawnictwo_ciagle.strony = None
    ret = wydawnictwo_ciagle.eksport_pbn_zakres_stron()
    assert ret == "35"


@pytest.mark.django_db
def test_eksport_pbn_get_issue(wydawnictwo_ciagle):
    wydawnictwo_ciagle.nr_zeszytu = "10"
    assert wydawnictwo_ciagle.eksport_pbn_get_issue() == "10"

    wydawnictwo_ciagle.nr_zeszytu = None
    wydawnictwo_ciagle.informacje = "1993 z. 5"
    assert wydawnictwo_ciagle.eksport_pbn_get_issue() == "5"


@pytest.mark.django_db
def test_eksport_pbn_get_volume(wydawnictwo_ciagle):
    wydawnictwo_ciagle.tom = "10"
    assert wydawnictwo_ciagle.eksport_pbn_get_volume() == "10"

    wydawnictwo_ciagle.tom = None
    wydawnictwo_ciagle.informacje = "1992 vol. 5"
    assert wydawnictwo_ciagle.eksport_pbn_get_volume() == "5"
