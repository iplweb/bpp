"""E2E Fazy 4: nowy autor (brak) + odpięcie autora spoza pliku.
LIVEOPS.RUNNER='eager' (settings/test.py) → enqueue() wykonuje run()
synchronicznie w ramach POST-a."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import STATUS_BRAK
from import_pracownikow.tests._helpers import unikalna_nazwa


@pytest.mark.django_db
def test_e2e_nowy_autor_i_odpiecie(admin_client, admin_user, yesterday):
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )

    # autor spoza pliku: jednostka zarządzana automatycznie + aktualna jednostka
    j_spoza = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Spoza"),
        skrot=unikalna_nazwa("Kat. Spoza"),
        zarzadzaj_automatycznie=True,
    )
    a_spoza = baker.make(Autor, nazwisko="Odpinalski", imiona="Marek")
    a_spoza.dodaj_jednostke(j_spoza)
    aj_spoza = a_spoza.autor_jednostka_set.get(jednostka=j_spoza)

    csv = (f"Osoba;Nazwa jednostki\nGrzegorz Nowakowski;{jednostka.nazwa}\n").encode()
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
    # Jednostka z pliku jest już w bazie, brak decyzji o tytułach → analiza
    # przeskakuje Krok 1 i ląduje w fazie osób. Decyzje osobowe (utwórz nowego,
    # odpięcie) rozstrzygamy niżej, już w Kroku 2.
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA

    row = imp.importpracownikowrow_set.get()
    assert row.confidence == STATUS_BRAK
    assert row.autor is None

    odp = imp.odpiecia.get(autor_jednostka=aj_spoza)
    assert odp.zaznaczone is False

    # user zaznacza „utwórz nowego" dla wiersza brak
    url_un = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    assert admin_client.post(url_un, {"utworz_nowego": "on"}).status_code == 200

    # user zaznacza odpięcie
    url_odp = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    assert admin_client.post(url_odp, {"zaznaczone": "on"}).status_code == 200

    # Struktura była już w bazie → analiza auto-przeszła do fazy osób (asercja
    # wyżej), więc zostaje sam import osób (Krok 2, zakres pelny).
    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    resp = admin_client.post(url_zatw, {"zakres": "pelny"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # nowy autor + jego AJ powstały
    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.nazwisko == "Nowakowski"
    assert Autor_Jednostka.objects.filter(autor=row.autor, jednostka=jednostka).exists()

    # zatrudnienie odpiętego zakończone (wczoraj) + odpięcie wykonane
    aj_spoza.refresh_from_db()
    odp.refresh_from_db()
    assert aj_spoza.zakonczyl_prace == yesterday
    assert aj_spoza.podstawowe_miejsce_pracy is False
    assert odp.wykonane is True
