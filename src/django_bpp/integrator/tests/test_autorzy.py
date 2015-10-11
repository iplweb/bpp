# -*- encoding: utf-8 -*-
from django.contrib.auth.models import Group

from django.core.urlresolvers import reverse
from model_mommy import mommy
from webtest import Upload
import os
from bpp.models.autor import Autor, Tytul
from bpp.models.struktura import Jednostka
from integrator.models import AUTOR_IMPORT_COLUMNS, AutorIntegrationFile, AutorIntegrationRecord
from integrator.tasks import read_xls_data, read_autor_import, import_data, analyze_data, integrate_data

integrator_test1_xlsx = os.path.join(
    os.path.dirname(__file__),
    "integrator.autorzy.test1.xlsx")


def test_upload(preauth_webtest_app, normal_django_user):
    normal_django_user.groups.add(Group.objects.get(name="wprowadzanie danych"))
    page = preauth_webtest_app.get(reverse('integrator:new')).maybe_follow()
    form = page.form
    form['file'] = Upload(integrator_test1_xlsx)
    res = form.submit().maybe_follow()
    assert "Plik został dodany" in res.content
    assert "integrator.test1" in res.content


def test_read_xls_data():
    file_contents = open(integrator_test1_xlsx, "rb").read()
    data = read_autor_import(file_contents)
    data = list(data)
    assert data[0]['nazwisko'] == 'Kowalski'
    assert len(data) == 4


def test_import_data(db):
    aif = mommy.make(AutorIntegrationFile)
    import_data(parent=aif,
                data=[{'tytul_skrot': 'foo',
                       'nazwisko': 'nazwisko',
                       'imie': 'imie',
                       'nazwa_jednostki': 'nazwa_jednostki',
                       'pbn_id': 'pbn_id'},
                      {'tytul_skrot': 'foo',
                       'nazwisko': 'nazwisko',
                       'imie': 'imie',
                       'nazwa_jednostki': 'nazwa_jednostki',
                       'pbn_id': 'pbn_id'}
                      ]
                )
    assert AutorIntegrationRecord.objects.all().count() == 2


def test_analyze_data_1(db):
    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id=100)

    assert air1.moze_byc_zintegrowany_automatycznie == False
    analyze_data(aif)
    air1 = AutorIntegrationRecord.objects.get(pk=air1.pk)
    assert air1.moze_byc_zintegrowany_automatycznie == False
    assert air1.extra_info == "Brak takiego autora"


def test_analyze_data_2(db):
    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id=100)

    Autor.objects.create(
        nazwisko='Kowalski',
        imiona='Jan'
    )

    assert air1.moze_byc_zintegrowany_automatycznie == False
    analyze_data(aif)
    air1 = AutorIntegrationRecord.objects.get(pk=air1.pk)
    assert air1.moze_byc_zintegrowany_automatycznie == False
    assert air1.extra_info.startswith("Brak takiej jednostki")


def test_analyze_data_3(db):
    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id=100)

    Autor.objects.create(
        nazwisko='Kowalski',
        imiona='Jan'
    )
    mommy.make(Jednostka, nazwa='I Zakład')

    assert air1.moze_byc_zintegrowany_automatycznie == False
    analyze_data(aif)
    air1 = AutorIntegrationRecord.objects.get(pk=air1.pk)
    assert air1.moze_byc_zintegrowany_automatycznie == False
    assert air1.extra_info == "Brak takiego tytulu"


def test_analyze_data_4(db):
    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id=100)

    Autor.objects.create(
        nazwisko='Kowalski',
        imiona='Jan'
    )
    Tytul.objects.create(
        skrot='dr',
        nazwa='doktor'
    )
    mommy.make(Jednostka, nazwa='I Zakład')

    assert air1.moze_byc_zintegrowany_automatycznie == False
    analyze_data(aif)
    air1 = AutorIntegrationRecord.objects.get(pk=air1.pk)
    assert air1.moze_byc_zintegrowany_automatycznie == True


def test_analyze_data_5_bledny_pbn(db):
    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id='xaa')

    Autor.objects.create(
        nazwisko='Kowalski',
        imiona='Jan'
    )
    Tytul.objects.create(
        skrot='dr',
        nazwa='doktor'
    )
    mommy.make(Jednostka, nazwa='I Zakład')

    assert air1.moze_byc_zintegrowany_automatycznie == False
    analyze_data(aif)
    air1 = AutorIntegrationRecord.objects.get(pk=air1.pk)
    assert air1.extra_info == "PBN_ID nie jest cyfra"


def test_analyze_data_6(db):
    a = Autor.objects.create(
        nazwisko='Kowalski',
        imiona='Jan',
        pbn_id=None
    )
    Tytul.objects.create(
        skrot='dr',
        nazwa='doktor'
    )
    mommy.make(Jednostka, nazwa='I Zakład')

    aif = mommy.make(AutorIntegrationFile)
    air1 = AutorIntegrationRecord.objects.create(
        parent=aif,
        tytul_skrot='dr',
        nazwisko='Kowalski',
        imie='Jan',
        nazwa_jednostki='I Zakład',
        pbn_id="100.0",

        matching_autor=Autor.objects.all()[0],
        matching_jednostka=Jednostka.objects.all()[0],
        zanalizowano=True,
        moze_byc_zintegrowany_automatycznie=True,
        zintegrowano=False)

    assert a.pbn_id == None
    integrate_data(aif)

    a = Autor.objects.get(pk=a.pk)
    assert a.pbn_id == 100

