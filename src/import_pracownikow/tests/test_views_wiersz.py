import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_RECZNY, STATUS_WIELU


def _wielu_row(owner):
    imp = baker.make(
        ImportPracownikow, owner=owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a2, pewnosc=1.0, powod="iexact"
    )
    return imp, row, a1


@pytest.mark.django_db
def test_wybor_kandydata_materializuje_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.wybrany_kandydat_id == a1.pk
    assert row.autor_id == a1.pk
    # Wybór kandydata = świadomy wybór operatora → status „ręczny" (item 7).
    assert row.confidence == STATUS_RECZNY
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_odrzuca_obcego_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    obcy = baker.make(Autor, nazwisko="Obcy", imiona="Ktoś")
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": obcy.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_wybor_kandydata_owner_scoped(client, django_user_model, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    inny = django_user_model.objects.create_user(
        username="inny", password="x", is_staff=True
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_wybor_kandydata_odrzucony_gdy_import_zintegrowany(admin_client, admin_user):
    # G3: bramka stanu — POST wyboru na wierszu importu już zintegrowanego
    # (retry HTMX / back-button / wyścig z Zatwierdź) MUSI dać 400 i NIE
    # nadpisać danych po commicie ani integrować drugi raz.
    imp, row, a1 = _wielu_row(admin_user)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save(update_fields=["stan"])
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_odtworz_autor_jednostka_zdejmuje_wpis_i_odklada_create():
    # G1 (jednostkowy): stary diff AJ dla POPRZEDNIEGO autora zostaje zdjęty,
    # a dla nowego autora BEZ istniejącego AJ odkładany jest świeży create.
    from bpp.models import Autor, Jednostka
    from import_pracownikow.pewnosc import odtworz_autor_jednostka

    imp = baker.make(ImportPracownikow)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")  # bez AJ
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=nowy,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    odtworz_autor_jednostka(row, nowy)
    assert row.autor_jednostka is None
    assert row.diff_do_utworzenia["autor_jednostka"]["autor"] == nowy.pk
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_nie_koruptuje_aj_starego_autora(admin_client, admin_user):
    # G1 (regresja korupcji): wiersz miał odłożony diff AJ dla STAREGO autora
    # (np. z wcześniejszej ścieżki analizy), a user wybiera NOWEGO kandydata,
    # który MA już Autor_Jednostka. Po wyborze uśpiony wpis starego autora musi
    # zniknąć — inaczej integracja utworzyłaby AJ dla starego i nadpisała
    # row.autor_jednostka (dane zatrudnienia nowego autora u starego).
    from bpp.models import Autor, Autor_Jednostka, Jednostka

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")
    aj_nowy = baker.make(Autor_Jednostka, autor=nowy, jednostka=jednostka)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=stary, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=nowy, pewnosc=1.0, powod="iexact"
    )
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": nowy.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == nowy.pk
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert row.autor_jednostka_id == aj_nowy.pk
    # stary autor nie dostał żadnego AJ (nie było i nie powstało)
    assert not Autor_Jednostka.objects.filter(autor=stary).exists()
