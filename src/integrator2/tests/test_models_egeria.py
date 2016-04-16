# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import os

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from model_mommy import mommy

from bpp.models.struktura import Uczelnia, Wydzial
from integrator2.models.egeria import zrob_skrot, UtworzWydzial, ZaktualizujWydzial, UsunWydzial, EgeriaImportElement, \
    today, EgeriaImportIntegration


def test_zrob_skrot():
    assert zrob_skrot("Stefan Lubi Jabłka i Cześć") == "SLJiC"


@pytest.mark.django_db
def test_UtworzWydzial():
    x = mommy.make(UtworzWydzial, nazwa="Foobar", uczelnia=None)
    assert x.needed() == True
    x.perform()
    assert Uczelnia.objects.all().count() == 1
    assert Wydzial.objects.all().count() == 1


@pytest.mark.django_db
def test_UtworzWydzial_jest_uczelnia():
    u = mommy.make(Uczelnia)
    x = mommy.make(UtworzWydzial, nazwa="Foobar", uczelnia=None)
    x.perform()
    assert Uczelnia.objects.all().count() == 1
    assert Wydzial.objects.all()[0].uczelnia == u


@pytest.mark.django_db
def test_UtworzWydzial_skrot_istnieje():
    mommy.make(Wydzial, nazwa="Foobar", skrot="F")
    x = mommy.make(UtworzWydzial, nazwa="Fpierwszy")
    x.perform()
    assert Wydzial.objects.all().count() == 2


@pytest.mark.django_db
def test_ZaktualizujWydzial():
    w = mommy.make(Wydzial, widoczny=False, zezwalaj_na_ranking_autorow=False)
    x = mommy.make(ZaktualizujWydzial, wydzial=w)
    assert x.needed()

    x.perform()
    w.refresh_from_db()
    assert w.widoczny == True
    assert w.zezwalaj_na_ranking_autorow == True


@pytest.mark.django_db
def test_UsunWydzial():
    w = mommy.make(Wydzial, widoczny=True)
    x = mommy.make(UsunWydzial, wydzial=w)

    assert x.needed() == True

    x.perform()
    w.refresh_from_db()
    assert w.widoczny == False


@pytest.mark.django_db
def test_EgeriaImportElement():
    ei = mommy.make(EgeriaImportElement)
    # test __iter__
    cnt = 0
    for elem in ei:
        cnt += 1
    assert cnt > 3


def test_today():
    assert today() != None


def make_egeria_integration(path):
    bn = os.path.basename(path)
    fp = os.path.join(os.path.dirname(__file__), path)
    return EgeriaImportIntegration.objects.create(
        name=bn,
        file=SimpleUploadedFile(bn, open(fp, 'rb').read()),
        owner=mommy.make(get_user_model())
    )


@pytest.fixture
def ei_initial():
    """
    :rtype: integrator2.models.egeria.EgeriaImportIntegration
    """
    return make_egeria_integration('xls/pracownicy/initial.xlsx')


@pytest.mark.django_db
def test_EgeriaImportIntegration_input_file_to_dict_stream(ei_initial):
    assert len(list(ei_initial.input_file_to_dict_stream())) > 5


@pytest.mark.django_db
def test_EgeriaImportIntegration_header_columns(ei_initial):
    assert len(ei_initial.header_columns()) > 3


@pytest.mark.django_db
def test_EgeriaImportIntegration_dict_stream_to_db(ei_initial):
    assert EgeriaImportElement.objects.all().count() == 0
    ei_initial.dict_stream_to_db()
    assert EgeriaImportElement.objects.all().count() > 5


@pytest.mark.django_db
def test_EgeriaImportIntegration_analizuj_wydzialy(ei_initial):
    assert UtworzWydzial.objects.filter(parent=ei_initial).count() == 0
    ei_initial.dict_stream_to_db()
    ei_initial.analizuj_wydzialy()
    assert UtworzWydzial.objects.filter(parent=ei_initial).count() == 4


@pytest.mark.django_db
def test_EgeriaImportIntegration_analizuj_wydzialy(ei_initial):
    assert UtworzWydzial.objects.filter(parent=ei_initial).count() == 0
    ei_initial.dict_stream_to_db()
    ei_initial.analizuj_wydzialy()
    assert UtworzWydzial.objects.filter(parent=ei_initial).count() == 4


@pytest.mark.django_db
def test_EgeriaImportIntegration_analizuj_wydzialy_zmienione(ei_initial):
    mommy.make(Wydzial, nazwa='I Wydział Lekarski z Oddziałem Stomatologicznym', widoczny=False,
               zezwalaj_na_ranking_autorow=False)
    ei_initial.dict_stream_to_db()
    ei_initial.analizuj_wydzialy()
    assert ZaktualizujWydzial.objects.all().count() == 1


@pytest.mark.django_db
def test_EgeriaImportIntegration_analizuj_wydzialy_usuniete(ei_initial):
    mommy.make(Wydzial, nazwa='Nie ma mnie w pliku')
    ei_initial.dict_stream_to_db()
    ei_initial.analizuj_wydzialy()
    assert UsunWydzial.objects.all().count() == 1
