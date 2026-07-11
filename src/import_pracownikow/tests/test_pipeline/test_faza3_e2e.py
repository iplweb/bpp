"""E2E Fazy 3: plik z kolumną sklejonej osoby + statusy pewności + wybór
kandydata. LIVEOPS.RUNNER='eager' (settings/test.py) → enqueue() wykonuje run()
synchronicznie w ramach POST-a."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_e2e_osoba_sklejona_status_i_wybor(admin_client, admin_user):
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr/doktor" → get_or_create.
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    # jeden jednoznaczny (twardy) + dwóch o identycznym imieniu (wielu)
    twardy = baker.make(
        Autor, nazwisko="Zielinski", imiona="Adam", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=twardy, jednostka=jednostka)
    dup1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    csv = (
        "Osoba;Nazwa jednostki\n"
        f"dr Adam Zielinski;{jednostka.nazwa}\n"
        f"dr Jan Kowalski;{jednostka.nazwa}\n"
    ).encode()
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    # mapowanie: Osoba → osoba_sklejona; analiza rusza eager w POST-cie
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url_map,
        {
            "kol__osoba": "osoba_sklejona",
            "kol__nazwa_jednostki": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY

    wiersze = {
        r.dane_znormalizowane["nazwisko"]: r for r in imp.importpracownikowrow_set.all()
    }
    assert wiersze["Zielinski"].confidence == STATUS_TWARDY
    assert wiersze["Zielinski"].autor_id == twardy.pk
    assert wiersze["Kowalski"].confidence == STATUS_WIELU
    assert wiersze["Kowalski"].autor is None
    assert wiersze["Kowalski"].kandydaci.count() == 2

    # wybór kandydata dla wiersza „wielu"
    url_wybor = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": wiersze["Kowalski"].pk},
    )
    resp = admin_client.post(url_wybor, {"wybrany_kandydat": dup1.pk})
    assert resp.status_code == 200
    wiersze["Kowalski"].refresh_from_db()
    assert wiersze["Kowalski"].autor_id == dup1.pk
    assert wiersze["Kowalski"].zmiany_potrzebne is True

    # Dwustopniowy commit: Krok 1 struktura → Krok 2 osoby (eager).
    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    admin_client.post(url_zatw, {"zakres": "jednostki"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    resp = admin_client.post(url_zatw, {"zakres": "pelny"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # F1: wybór kandydata dup1 odtworzył powiązanie AJ (diff_do_utworzenia), więc
    # integracja UTWORZYŁA Autor_Jednostka (dup1, jednostka) i NIE rzuciła
    # AttributeError w _integrate_autor_jednostka.
    assert Autor_Jednostka.objects.filter(autor=dup1, jednostka=jednostka).exists()
