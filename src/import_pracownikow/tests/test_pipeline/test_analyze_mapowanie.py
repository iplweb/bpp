import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress

from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


@pytest.mark.django_db
def test_analiza_z_mapowaniem_inaczej_nazwanych_kolumn(
    admin_user, dwa_autory_z_jednostka
):
    autor, jednostka = dwa_autory_z_jednostka
    # plik z NIESTANDARDOWYMI nazwami kolumn — bez mapowania nie zadziała
    csv = (
        f"Nazwisko;Imie;Jedn org\n{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode()
    imp = ImportPracownikow(
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZMAPOWANY,
        mapowanie_kolumn={
            "nazwisko": "nazwisko",
            "imie": "imię",
            "jedn_org": "nazwa_jednostki",
        },
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    analizuj(imp, MockProgress(imp))

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk


@pytest.mark.django_db
def test_analiza_puste_mapowanie_zachowuje_zachowanie_fazy1(
    admin_user, dwa_autory_z_jednostka
):
    # plik ze standardowymi nazwami + puste mapowanie → działa jak w Fazie 1
    autor, jednostka = dwa_autory_z_jednostka
    csv = (
        "Nazwisko;Imię;Nazwa jednostki\n"
        f"{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode()
    imp = ImportPracownikow(
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZMAPOWANY,
        mapowanie_kolumn={},
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    analizuj(imp, MockProgress(imp))
    imp.refresh_from_db()
    assert imp.importpracownikowrow_set.get().autor_id == autor.pk
