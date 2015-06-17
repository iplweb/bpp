# -*- encoding: utf-8 -*-

from django.db import connection
import pytest
from bpp.models.cache import Rekord, Autorzy
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


def test_uczelnia(uczelnia):
    assert uczelnia != None


def test_wydzial(wydzial):
    assert wydzial != None


def test_wydawnictwo_ciagle(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle != None


def test_autorzy(autor_jan_nowak, autor_jan_kowalski):
    assert autor_jan_kowalski != None
    assert autor_jan_nowak != None


def test_jednostka(jednostka):
    assert jednostka != None


def test_zrodlo(zrodlo):
    assert zrodlo != None


def test_wydawnictwo_ciagle(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle != None


def test_wydawnictwo_zwarte(wydawnictwo_zwarte):
    assert wydawnictwo_zwarte != None


def test_doktorat(doktorat):
    assert doktorat != None


def test_habilitacja(habilitacja):
    assert habilitacja != None


def test_patent(patent):
    assert patent != None


def test_preauth_webtest_app(preauth_webtest_app):
    assert preauth_webtest_app != None
    res = preauth_webtest_app.get("/admin/").follow()
    assert 'Zaloguj si' in res.content


def test_preauth_webtest_admin_app(preauth_webtest_admin_app):
    assert preauth_webtest_admin_app != None
    res = preauth_webtest_admin_app.get("/admin/")
    assert 'Administracja stron' in res.content


def test_praca_doktorska_view(doktorat):
    # Jeżeli nie ma charatkeruy formalnego 'D', to sie to nie pokaze
    cur = connection.cursor()
    cur.execute("SELECT * FROM bpp_praca_doktorska_view")
    assert len(cur.fetchall()) == 1


def test_praca_habilitacyjna_view(habilitacja):
    # Jeżeli nie ma charatkeruy formalnego 'H', to sie to nie pokaze
    cur = connection.cursor()
    cur.execute("SELECT * FROM bpp_praca_habilitacyjna_view")
    assert len(cur.fetchall()) == 1


def test_patent_view(patent):
    # Jeżeli nie ma charatkeruy formalnego 'PAT' oraz typu KBN PO oraz jezyka 'pol.', to sie to nie pokaze
    cur = connection.cursor()
    cur.execute("SELECT * FROM bpp_patent_view")
    assert len(cur.fetchall()) == 1

def test_wydawnictwo_ciagle_z_dwoma_autorami(wydawnictwo_ciagle_z_dwoma_autorami):
    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle_Autor.objects.all().count() == 2
    assert Autorzy.objects.count() == 2
    