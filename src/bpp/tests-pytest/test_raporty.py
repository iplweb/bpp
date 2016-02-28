# -*- encoding: utf-8 -*-

import pytest
from django.core.urlresolvers import reverse
from model_mommy import mommy

from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.views.raporty.raport_aut_jed_common import get_base_query_autor, raport_autorow_tabela


@pytest.mark.django_db
def test_bug_raport_roczny_autorow_pkt_2_2_2_6_issue_441(autor_jan_kowalski, jednostka, obiekty_bpp):
    # http://mantis.iplweb.pl/view.php?id=441

    ksp = obiekty_bpp.charakter_formalny["KSP"]
    pol = obiekty_bpp.jezyk["pol."]

    praca_2_2 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, rok=2015)
    praca_2_2.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    praca_2_6 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, jezyk=pol, rok=2015)
    praca_2_6.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red.")

    base_query = get_base_query_autor(autor=autor_jan_kowalski, rok_min=2015, rok_max=2015)

    tabela_2_2 = raport_autorow_tabela("2_2", base_query, autor_jan_kowalski).count()
    assert tabela_2_2 == 1

    tabela_2_6 = raport_autorow_tabela("2_6", base_query, autor_jan_kowalski).count()
    assert tabela_2_6 == 1


@pytest.mark.django_db
def test_bug_raport_roczny_autorow_pkt_2_1_2_5_issue_441(autor_jan_kowalski, jednostka, obiekty_bpp):
    # http://mantis.iplweb.pl/view.php?id=441

    ksz = obiekty_bpp.charakter_formalny["KSZ"]
    ang = obiekty_bpp.jezyk["ang."]

    praca_2_1 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksz, jezyk=ang, rok=2015)
    praca_2_1.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    praca_2_5 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksz, jezyk=ang, rok=2015)
    praca_2_5.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red.")

    base_query = get_base_query_autor(autor=autor_jan_kowalski, rok_min=2015, rok_max=2015)

    tabela_2_1 = raport_autorow_tabela("2_1", base_query, autor_jan_kowalski).count()
    assert tabela_2_1 == 1

    tabela_2_5 = raport_autorow_tabela("2_5", base_query, autor_jan_kowalski).count()
    assert tabela_2_5 == 1


def test_raport_autorow(app, autor_jan_kowalski, jednostka, obiekty_bpp):
    ksp = obiekty_bpp.charakter_formalny["KSP"]
    pol = obiekty_bpp.jezyk["pol."]

    praca_2_2 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, rok=2015)
    praca_2_2.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    praca_2_6 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, jezyk=pol, rok=2015)
    praca_2_6.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red.")

    page = app.get(reverse("bpp:raport-autorow", args=(autor_jan_kowalski.pk, 2015)))
    assert page.status_code == 200


def test_raport_jednostek(app, autor_jan_kowalski, jednostka, obiekty_bpp):
    ksp = obiekty_bpp.charakter_formalny["KSP"]
    pol = obiekty_bpp.jezyk["pol."]

    praca_2_2 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, rok=2015)
    praca_2_2.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    page = app.get(reverse("bpp:raport-jednostek", args=(jednostka.pk, 2015)))
    assert page.status_code == 200
