# -*- encoding: utf-8 -*-

import pytest


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
