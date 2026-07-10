import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


def _autor_z_aktualna(nazwa="Stara"):
    stara = baker.make(Jednostka, nazwa=nazwa, skrot=nazwa[:2].upper())
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    return autor, stara


def _import(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(ImportPracownikow, owner=owner, stan=stan)


@pytest.mark.django_db
def test_toggle_przepnij_prace_ustawia_flage(admin_client, admin_user):
    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.przepnij_prace is True

    resp = admin_client.post(url, {})
    row.refresh_from_db()
    assert row.przepnij_prace is False


@pytest.mark.django_db
def test_toggle_blokada_poza_podgladem(admin_client, admin_user):
    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_bulk_zaznacza_tylko_wiersze_z_roznica(admin_client, admin_user):
    # UWAGA: różni autorzy dla row_diff i row_same — inaczej jednostka „stara”
    # autora z row_diff stałaby się parą Z PLIKU (przez row_same) i guard F1
    # słusznie by ją odrzucił. Tu izolujemy sam warunek różnicy jednostki.
    autor_diff, stara_diff = _autor_z_aktualna("Sda")
    autor_same, stara_same = _autor_z_aktualna("Ssa")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    # różnica jednostki, stara jednostka NIE w innym wierszu → zaznaczony
    row_diff = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor_diff, jednostka=nowa, zmiany_potrzebne=False
    )
    # brak różnicy (jednostka == aktualna) → NIE zaznaczony
    row_same = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor_same,
        jednostka=stara_same,
        zmiany_potrzebne=False,
    )
    # bez autora → NIE zaznaczony
    row_bez = ImportPracownikowRow.objects.create(
        parent=imp, autor=None, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse("import_pracownikow:zaznacz-przepiecia", kwargs={"pk": imp.pk})
    resp = admin_client.post(url)
    assert resp.status_code == 302
    for row, oczekiwane in (
        (row_diff, True),
        (row_same, False),
        (row_bez, False),
    ):
        row.refresh_from_db()
        assert row.przepnij_prace is oczekiwane


@pytest.mark.django_db
def test_bulk_pomija_wiersz_gdy_stara_jednostka_w_pliku(admin_client, admin_user):
    # F1: autor z etatem w „stara” potwierdzonym osobnym wierszem pliku
    # (jednostka=stara) ORAZ wierszem z różnicą (jednostka=nowa). Bulk NIE
    # zaznacza wiersza-różnicy — stara jednostka jest parą Z PLIKU.
    autor, stara = _autor_z_aktualna("Pul")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    row_a = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    row_b = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse("import_pracownikow:zaznacz-przepiecia", kwargs={"pk": imp.pk})
    resp = admin_client.post(url)
    assert resp.status_code == 302
    row_a.refresh_from_db()
    row_b.refresh_from_db()
    assert row_a.przepnij_prace is False
    assert row_b.przepnij_prace is False  # guard „para z pliku”


@pytest.mark.django_db
def test_kolumna_widoczna_tylko_przy_roznicy_jednostki(admin_client, admin_user):
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor

    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
    imp = _import(admin_user)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    # dodatkowo import ma finished_successfully, by tabela się wyrenderowała
    ImportPracownikow.objects.filter(pk=imp.pk).update(finished_successfully=True)
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    content = resp.content.decode("utf-8")
    assert "przepnij_prace" in content
    assert "(1 prac)" in content


@pytest.mark.django_db
def test_toggle_wlaczenie_niekwalifikujacego_400(admin_client, admin_user):
    # G7/F2: włączenie przepięcia na wierszu BEZ różnicy jednostki
    # (jednostka == aktualna) → 400, flaga NIEZMIENIona.
    autor, stara = _autor_z_aktualna()
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.przepnij_prace is False


@pytest.mark.django_db
def test_toggle_odznaczenie_niekwalifikujacego_dozwolone(admin_client, admin_user):
    # G2: wiersz, który przestał się kwalifikować (jednostka == aktualna), z
    # flagą-zombie przepnij_prace=True musi dać się ODZNACZYĆ — odznaczanie nie
    # waliduje kwalifikacji (inaczej flagi nie dałoby się zdjąć).
    autor, stara = _autor_z_aktualna()
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=stara,
        zmiany_potrzebne=False,
        przepnij_prace=True,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.przepnij_prace is False
