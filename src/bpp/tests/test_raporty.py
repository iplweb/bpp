# -*- encoding: utf-8 -*-

import pytest
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from model_mommy import mommy

from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.views.raporty.raport_aut_jed_common import get_base_query_autor, raport_autorow_tabela


def test_raport_autorow(app, autor_jan_kowalski, jednostka, standard_data):
    ksp = Charakter_Formalny.objects.get(skrot="KSP")
    pol = Jezyk.objects.get(skrot="pol.")

    praca_2_2 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, rok=2015)
    praca_2_2.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    praca_2_6 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, jezyk=pol, rok=2015)
    praca_2_6.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red.")

    page = app.get(reverse("bpp:raport-autorow", args=(autor_jan_kowalski.pk, 2015)))
    assert page.status_code == 200


def test_raport_jednostek(app, autor_jan_kowalski, jednostka, standard_data):
    ksp = Charakter_Formalny.objects.get(skrot="KSP")
    pol = Jezyk.objects.get(skrot="pol.")

    praca_2_2 = mommy.make(Wydawnictwo_Zwarte, punkty_kbn=5, charakter_formalny=ksp, rok=2015)
    praca_2_2.dodaj_autora(autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    page = app.get(reverse("bpp:raport-jednostek", args=(jednostka.pk, 2015)))
    assert page.status_code == 200


@pytest.mark.django_db
def test_raport_aut_jed_1_4(standard_data, autor_jan_kowalski, jednostka):
    base_query = get_base_query_autor(autor=autor_jan_kowalski, rok_min=0, rok_max=9999)
    tabela_1_4 = raport_autorow_tabela("1_4", base_query, autor_jan_kowalski)

@pytest.mark.django_db
def test_raport_autorow_msword(standard_data, autor_jan_kowalski, webtest_app):
    res = webtest_app.get(reverse("bpp:raport-autorow", args=(autor_jan_kowalski.pk, 2016)) + "?output=msw")
    assert res.content_type == "application/msword"
    assert res.status_code == 200
