from django.db import transaction
from django.urls import reverse

from import_dyscyplin.models import Import_Dyscyplin, Import_Dyscyplin_Row


def wyslij(wd_app, plik):
    assert Import_Dyscyplin.objects.all().count() == 0
    c = wd_app.get(reverse("import_dyscyplin:create")).maybe_follow()
    c.forms[0]["plik"].value = [
        plik,
    ]
    res = c.forms[0].submit().maybe_follow()
    assert Import_Dyscyplin.objects.all().count() == 1

    return res


def wyslij_i_przeanalizuj(wd_app, plik):
    wyslij(wd_app, plik)

    i = Import_Dyscyplin.objects.all().first()
    i.stworz_kolumny()

    if not i.stan == Import_Dyscyplin.STAN.BLEDNY:
        i.zatwierdz_kolumny()

        if not i.stan == Import_Dyscyplin.STAN.BLEDNY:
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
    i.stworz_kolumny()
    i.zatwierdz_kolumny()
    i.save()

    g = wd_app.get(reverse("import_dyscyplin:przetwarzaj", args=(i.pk,)))
    assert g.json["status"] == "ok"


def test_UsunImport_Dyscyplin(wd_app, test1_xlsx, transactional_db):
    wyslij(wd_app, test1_xlsx)
    assert Import_Dyscyplin.objects.all().count() == 1
    i = Import_Dyscyplin.objects.all().first()
    g = wd_app.get(reverse("import_dyscyplin:usun", args=(i.pk,))).maybe_follow()
    assert "Brak informacji o importowanych" in g.testbody
    assert Import_Dyscyplin.objects.all().count() == 0


def test_API_Do_IntegracjiView(wd_app, test1_xlsx, autor_jan_nowak):
    i = wyslij_i_przeanalizuj(wd_app, test1_xlsx)
    i.integruj_dyscypliny()

    r = Import_Dyscyplin_Row.objects.all().first()
    r.autor = autor_jan_nowak
    r.stan = Import_Dyscyplin_Row.STAN.NOWY
    r.save()

    res = wd_app.get(reverse("import_dyscyplin:api_do_integracji", args=(i.pk,)))
    assert len(res.json["data"]) == 1
    assert res.json["data"][0]["nazwisko"] == "Kowalski"


def test_API_Nie_Do_IntegracjiView(wd_app, test1_xlsx):
    i = wyslij_i_przeanalizuj(wd_app, test1_xlsx)

    res = wd_app.get(reverse("import_dyscyplin:api_nie_do_integracji", args=(i.pk,)))
    assert len(res.json["data"]) == 6


def test_API_Zintegrowane(wd_app, test1_xlsx):
    i = wyslij_i_przeanalizuj(wd_app, test1_xlsx)

    r = Import_Dyscyplin_Row.objects.all().first()
    r.stan = Import_Dyscyplin_Row.STAN.ZINTEGROWANY
    r.save()

    res = wd_app.get(reverse("import_dyscyplin:api_zintegrowane", args=(i.pk,)))
    assert len(res.json["data"]) == 1


def test_UruchomIntegracjeImport_DyscyplinView(
    wd_app, wprowadzanie_danych_user, test1_xlsx
):
    i = wyslij_i_przeanalizuj(wd_app, test1_xlsx)
    i.integruj_dyscypliny()
    i.owner = wprowadzanie_danych_user
    i.save()

    res = wd_app.get(reverse("import_dyscyplin:integruj", args=(i.pk,)))
    assert res.json["status"] == "ok"
