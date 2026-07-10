"""E2E Fazy 2: upload pliku z NIESTANDARDOWYMI nazwami kolumn → ekran
mapowania (POST) → stan zmapowany → analiza (eager enqueue) → wiersze.

W testach LIVEOPS.RUNNER="eager" (settings/test.py), więc ``enqueue()`` w
``MapowanieView.form_valid`` wykonuje ``run()`` SYNCHRONICZNIE — analiza
odpala się w ramach POST-a, bez ręcznego ``run()``."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_e2e_upload_mapowanie_analiza(admin_client, admin_user, dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    csv = (
        f"Nazwisko;Imie;Jedn org\n{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode()
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    # ekran mapowania: POST z korektą (Imie→imię, Jedn org→nazwa_jednostki).
    # Pod eager runnerem enqueue() z form_valid od razu wykona analizę.
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {
            "kol__nazwisko": "nazwisko",
            "kol__imie": "imię",
            "kol__jedn_org": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    # analiza wykonana eager w ramach POST-a:
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk
