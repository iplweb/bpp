# -*- encoding: utf-8 -*-
import re

import pytest
from django.core.exceptions import ValidationError
from django.views.generic.dates import timezone_today
from lxml.etree import Element
from model_mommy import mommy

from bpp.admin import Wersja_Tekstu_OpenAccessAdmin
from bpp.models import (
    Autor_Dyscyplina,
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
    Typ_Odpowiedzialnosci,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle_Autor,
    parse_informacje_as_dict,
)
from bpp.models.konferencja import Konferencja
from bpp.models.nagroda import Nagroda
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Jednostka, Wydzial
from bpp.models.system import Charakter_Formalny, Charakter_PBN, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


@pytest.mark.django_db
def test_baza_modelu_odpowiedzialnosci_zapisywanie(
    wydawnictwo_ciagle,
    autor_jan_nowak,
    rok,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    typy_odpowiedzialnosci,
    db,
):
    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()

    ad = Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        procent_dyscypliny=50,
    )

    wca = Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=wydawnictwo_ciagle,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        zapisany_jako="Foobar",
        dyscyplina_naukowa=None,
    )
    wca.save()

    wca.clean()

    wca.dyscyplina_naukowa = dyscyplina2
    with pytest.raises(ValidationError):
        wca.clean()

    wca.dyscyplina_naukowa = dyscyplina1
    wydawnictwo_ciagle.rok = 50
    wydawnictwo_ciagle.save()
    with pytest.raises(ValidationError):
        wca.clean()

    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()
    wca.clean()

    ad.dyscyplina_naukowa = dyscyplina2
    ad.subdyscyplina_naukowa = dyscyplina1
    ad.save()
    wca.clean()


@pytest.mark.django_db
def test_baza_modelu_odpowiedzialnosci_autorow_dyscyplina_okresl_dyscypline(
    wydawnictwo_ciagle,
    jednostka,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    typy_odpowiedzialnosci,
    rok,
):
    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, zapisany_jako="Kowalski"
    )
    assert wca.okresl_dyscypline() is None

    Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    assert wca.okresl_dyscypline() is None

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()
    assert wca.okresl_dyscypline() == dyscyplina2

    wca.dyscyplina_naukowa = None
    wca.save()
    assert wca.okresl_dyscypline() is None


@pytest.mark.django_db
def test_eksport_pbn_outstanding():
    wz = mommy.make(
        Wydawnictwo_Zwarte, praca_wybitna=True, uzasadnienie_wybitnosci="foobar"
    )
    toplevel = Element("test")
    wz.eksport_pbn_outstanding(toplevel)
    assert len(toplevel.getchildren()) == 2

    wz.praca_wybitna = False
    toplevel = Element("test")
    wz.eksport_pbn_outstanding(toplevel)
    assert len(toplevel.getchildren()) == 1


@pytest.mark.django_db
def test_eksport_pbn_outstanding_2():
    wz = mommy.make(Wydawnictwo_Zwarte)

    toplevel = Element("test")
    wz.eksport_pbn_award(toplevel)
    assert len(toplevel.getchildren()) == 0

    mommy.make(Nagroda, object=wz, rok_przyznania=2000, uzasadnienie="foobar")

    mommy.make(Nagroda, object=wz, rok_przyznania=2001, uzasadnienie="baz quux")

    toplevel = Element("test")
    wz.eksport_pbn_award(toplevel)
    assert len(toplevel.getchildren()) == 2


@pytest.mark.django_db
def test_eksport_pbn_issn():
    wz = mommy.make(Wydawnictwo_Zwarte, issn="foobar")

    toplevel = Element("test")
    wz.eksport_pbn_issn(toplevel)
    assert len(toplevel.getchildren())

    wz.issn = None
    toplevel = Element("test")
    wz.eksport_pbn_issn(toplevel)
    assert len(toplevel.getchildren()) == 0


@pytest.mark.django_db
def test_eksport_pbn_seria():
    s = mommy.make(Seria_Wydawnicza, nazwa="TEST")
    wz = mommy.make(Wydawnictwo_Zwarte, seria_wydawnicza=s, numer_w_serii="15")

    toplevel = Element("test")
    wz.eksport_pbn_series(toplevel)
    wz.eksport_pbn_number_in_series(toplevel)
    assert len(toplevel.getchildren()) == 2

    wz.seria_wydawnicza = None
    wz.numer_w_serii = None
    wz.save()

    toplevel = Element("test")
    wz.eksport_pbn_series(toplevel)
    wz.eksport_pbn_number_in_series(toplevel)
    assert len(toplevel.getchildren()) == 0


@pytest.mark.django_db
def test_eksport_pbn_conference():
    konf = mommy.make(Konferencja)
    wc = mommy.make(Wydawnictwo_Zwarte, konferencja=konf)
    toplevel = Element("test")
    wc.eksport_pbn_conference(toplevel)
    assert len(toplevel.getchildren())


@pytest.mark.django_db
def test_eksport_pbn_is():
    c_pbn = mommy.make(Charakter_PBN, identyfikator="fubar")
    c = mommy.make(Charakter_Formalny, charakter_pbn=c_pbn)

    c_pbn2 = mommy.make(Charakter_PBN, identyfikator="baz")
    t = mommy.make(Typ_KBN, charakter_pbn=c_pbn2)

    wz = mommy.make(Wydawnictwo_Zwarte, charakter_formalny=c, typ_kbn=t)

    toplevel = Element("test")
    wz.eksport_pbn_is(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == "fubar"

    c.charakter_pbn = None
    c.save()

    toplevel = Element("test")
    wz.eksport_pbn_is(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == "baz"

    t.charakter_pbn = None
    t.save()

    toplevel = Element("test")
    wz.eksport_pbn_is(toplevel=toplevel)
    with pytest.raises(IndexError):
        assert toplevel.getchildren()[0]


@pytest.mark.parametrize(
    "klass, pbn_id,expected",
    [
        (Wydawnictwo_Ciagle, 500, "500"),
        (Wydawnictwo_Ciagle, None, "2000000100"),
        (Wydawnictwo_Zwarte, None, "4000000100"),
    ],
)
@pytest.mark.django_db
def test_eksport_pbn_system_identifier(klass, pbn_id, expected):
    wc = mommy.make(klass, pbn_id=pbn_id, pk=100)
    toplevel = Element("test")
    wc.eksport_pbn_system_identifier(toplevel=toplevel)
    assert toplevel.getchildren()[0].text == expected


@pytest.mark.django_db
def test_eksport_pbn_editor_afiliacja_w_kontekscie_wydzialu(
    uczelnia, autor_jan_kowalski, wydawnictwo_zwarte, typy_odpowiedzialnosci
):
    w1 = mommy.make(Wydzial, uczelnia=uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=uczelnia)

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=uczelnia)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=uczelnia)

    # Przypisz autora do DWÓCH jednostek z różnych wydziałów
    autor_jan_kowalski.dodaj_jednostke(j1)
    autor_jan_kowalski.dodaj_jednostke(j2)

    # W pracy określ afiliację do drugiego wydziału
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, j2, typ_odpowiedzialnosci_skrot="red."
    )

    # I teraz ma wyrzucić wszystkich redaktorów
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1

    # Zaś dla drugiego wydziału też wszyscy
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1


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
        ("s. xiii-xiv.", "xiii-xiv"),
    ],
)
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


@pytest.mark.django_db
def test_eksport_pbn_open_access_nic(wydawnictwo_zwarte):
    toplevel = Element("test")
    assert len(toplevel.getchildren()) == 0
    wydawnictwo_zwarte.eksport_pbn_open_access(toplevel)
    assert len(toplevel.getchildren()) == 0


@pytest.mark.django_db
def test_eksport_pbn_open_access(wydawnictwo_zwarte, openaccess_data):
    wydawnictwo_zwarte.openaccess_wersja_tekstu = (
        Wersja_Tekstu_OpenAccess.objects.first()
    )
    wydawnictwo_zwarte.openaccess_licencja = Licencja_OpenAccess.objects.first()

    wydawnictwo_zwarte.openaccess_czas_publikacji = (
        Czas_Udostepnienia_OpenAccess.objects.first()
    )

    wydawnictwo_zwarte.openaccess_ilosc_miesiecy = 5

    wydawnictwo_zwarte.openaccess_tryb_dostepu = (
        Tryb_OpenAccess_Wydawnictwo_Zwarte.objects.first()
    )

    wydawnictwo_zwarte.public_dostep_dnia = timezone_today()

    wydawnictwo_zwarte.save()

    toplevel = Element("test")
    wydawnictwo_zwarte.eksport_pbn_open_access(toplevel)
    assert len(toplevel.getchildren()[0].getchildren()) == 6


@pytest.mark.parametrize(
    "input,exp_rok,exp_tom,exp_nr",
    [
        ("1960", "1960", None, None),
        ("1960 t. 8", "1960", "8", None),
        ("1960 t 8", "1960", "8", None),
        ("1960 nr 2", "1960", None, "2"),
        ("1960 nr. 2", "1960", None, "2"),
        ("1960 t. 8 nr 2", "1960", "8", "2"),
        ("1960 T. 8 nr 2", "1960", "8", "2"),
        ("1960 T.8nr2", "1960", "8", "2"),
        ("1960 T.8 nr 2", "1960", "8", "2"),
        ("2018 Vol.77 suppl.2", "2018", "77", "suppl.2"),
        ("2020 T. [59] supl.", "2020", "59", "supl."),
        ("2020 Vol.61 no.7-12 supl.5", "2020", "61", "7-12 supl.5"),
        ("2020 Vol. A74 [suppl.]", "2020", "A74", "[suppl.]"),
        ("2020 voL 54 SuPPl. 45", "2020", "54", "SuPPl. 45"),
        ("2018 Vol.48 suppl.", "2018", "48", "suppl."),
        ("2020 Vol.60 supl.3", "2020", "60", "supl.3"),
        ("2020 supl. 2/1", "2020", None, "supl. 2/1"),
        ("2018 Vol.72 no.13 suppl.B", "2018", "72", "13 suppl.B"),
        ("2018 Vol.35 e-suppl.56", "2018", "35", "e-suppl.56"),
        ("2020 Vol.61 no.2 suppl.2", "2020", "61", "2 suppl.2"),
        ("2020 Vol.15 no.5 suppl.", "2020", "15", "5 suppl."),
        ("1998 Vol.4 suppl.2, fig., bibliogr. 11 poz., summ.", "1998", "4", "suppl.2"),
    ],
)
def test_parse_informacje(input, exp_rok, exp_tom, exp_nr):
    res = parse_informacje_as_dict(input)
    assert res.get("rok") == exp_rok
    assert res.get("tom") == exp_tom
    assert res.get("numer") == exp_nr
