import pytest
from django.db import connection

from bpp.models.cache import Autorzy, Rekord
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


def test_uczelnia(uczelnia):
    assert uczelnia is not None


def test_wydzial(wydzial):
    assert wydzial is not None


@pytest.mark.django_db
def test_wydawnictwo_ciagle(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle is not None


def test_autorzy(autor_jan_nowak, autor_jan_kowalski):
    assert autor_jan_kowalski is not None
    assert autor_jan_nowak is not None


def test_jednostka(jednostka):
    assert jednostka is not None


def test_zrodlo(zrodlo):
    assert zrodlo is not None


@pytest.mark.django_db
def test_wydawnictwo_zwarte(wydawnictwo_zwarte):
    assert wydawnictwo_zwarte is not None


def test_doktorat(doktorat):
    assert doktorat is not None


def test_habilitacja(habilitacja):
    assert habilitacja is not None


def test_patent(patent):
    assert patent is not None


@pytest.mark.uruchom_tylko_bez_microsoft_auth
def test_preauth_webtest_app(app):
    assert app is not None
    res = app.get("/admin/").follow()
    assert "Zaloguj się" in res.text


def test_admin_app(admin_app):
    assert admin_app is not None
    res = admin_app.get("/admin/")
    assert "Redagowanie" in res.text


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


@pytest.mark.django_db
def test_patent_view(patent):
    # Jeżeli nie ma charatkeruy formalnego 'PAT' oraz typu KBN PO oraz jezyka 'pol.', to sie to nie pokaze
    cur = connection.cursor()
    cur.execute("SELECT * FROM bpp_patent_view")
    assert len(cur.fetchall()) == 1


@pytest.mark.django_db
def test_wydawnictwo_ciagle_z_dwoma_autorami(wydawnictwo_ciagle_z_dwoma_autorami):
    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle_Autor.objects.all().count() == 2
    assert Autorzy.objects.count() == 2
