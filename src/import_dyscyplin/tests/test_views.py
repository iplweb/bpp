from django.db import transaction
from django.urls import reverse

from import_dyscyplin.models import Import_Dyscyplin


def extract_messageCookieId(html_source):
    return html_source.split("tests_need_this:messageCookieID:")[1][:36]


def wyslij(wd_app, plik):
    assert Import_Dyscyplin.objects.all().count() == 0
    c = wd_app.get(reverse("import_dyscyplin:create")).maybe_follow()
    c.forms[0]['plik'].value = [plik, ]
    c.forms[0]['web_page_uid'] = extract_messageCookieId(c.testbody)
    res = c.forms[0].submit().maybe_follow()
    assert Import_Dyscyplin.objects.all().count() == 1

    return res


def wyslij_i_przeanalizuj(wd_app, plik):
    wyslij(wd_app, plik)

    i = Import_Dyscyplin.objects.all().first()
    i.przeanalizuj()
    i.save()

    return i


def test_CreateImport_DyscyplinView_bledny_plik(wd_app, conftest_py, transactional_db):
    with transaction.atomic():
        wyslij_i_przeanalizuj(wd_app, conftest_py)

    assert Import_Dyscyplin.objects.all().count() == 1
    i = Import_Dyscyplin.objects.all().first()
    assert i.bledny == True
    assert i.stan == Import_Dyscyplin.STAN.BLEDNY


def test_CreateImport_DyscyplinView_dobry_plik(wd_app, test1_xlsx, transactional_db):
    with transaction.atomic():
        wyslij_i_przeanalizuj(wd_app, test1_xlsx)

    assert Import_Dyscyplin.objects.all().count() == 1
    i = Import_Dyscyplin.objects.all().first()
    assert i.bledny == False
    assert i.stan == Import_Dyscyplin.STAN.PRZEANALIZOWANY


def test_ListImport_Dyscyplin(wd_app, test1_xlsx):
    wyslij_i_przeanalizuj(wd_app, test1_xlsx)
    res = wd_app.get(reverse("import_dyscyplin:index"))
    assert "test1" in res.testbody
    assert ".xlsx" in res.testbody


def test_UruchomPrzetwarzanieImport_Dyscyplin(wd_app, test1_xlsx):
    wyslij(wd_app, test1_xlsx)

    i = Import_Dyscyplin.objects.all().first()
    g = wd_app.get(reverse("import_dyscyplin:przetwarzaj", args=(i.pk,)))
    assert g.json['status'] == "ok"


def test_UsunImport_Dyscyplin(wd_app, test1_xlsx, transactional_db):
    wyslij(wd_app, test1_xlsx)
    assert Import_Dyscyplin.objects.all().count() == 1
    i = Import_Dyscyplin.objects.all().first()
    g = wd_app.get(reverse("import_dyscyplin:usun", args=(i.pk,))).maybe_follow()
    assert "Brak informacji o importowanych" in g.testbody
    assert Import_Dyscyplin.objects.all().count() == 0
