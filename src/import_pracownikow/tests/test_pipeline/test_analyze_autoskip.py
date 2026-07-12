"""Skrót Krok 1 → Krok 2: gdy WSZYSTKIE jednostki i tytuły z pliku są już w
bazie (twarde dopasowania → zero decyzji strukturalnych), analiza pomija Krok 1
i ląduje od razu w fazie osób (``struktura_zintegrowana``). Gdy jest cokolwiek do
utworzenia/rozstrzygnięcia — normalny Krok 1 (``przeanalizowany``) i dwustopniowy
commit.

LIVEOPS.RUNNER='eager' (settings/test.py) → enqueue() wykonuje run()
synchronicznie w POST-cie mapowania."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow


def _upload_i_zmapuj(admin_client, admin_user, csv_bytes, *, tworz_jednostki):
    """Upload + POST mapowania (Osoba/Nazwa jednostki) → analiza eager. Zwraca
    odświeżony import."""
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv_bytes)
    imp.save()
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    dane = {
        "kol__osoba": "osoba_sklejona",
        "kol__nazwa_jednostki": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
    }
    if tworz_jednostki:
        dane["tworz_brakujace_jednostki"] = "on"
    resp = admin_client.post(url_map, dane)
    assert resp.status_code == 302
    imp.refresh_from_db()
    return imp


@pytest.mark.django_db
def test_wszystko_zmatchowane_przeskakuje_do_kroku2(admin_client, admin_user):
    """Jednostka i tytuł z pliku są już w bazie → analiza ustawia od razu
    ``struktura_zintegrowana`` (Krok 2), bez decyzji o jednostkach/tytułach."""
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    autor = baker.make(
        Autor, nazwisko="Zielinski", imiona="Adam", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)

    csv = (f"Osoba;Nazwa jednostki\ndr Adam Zielinski;{jednostka.nazwa}\n").encode()
    imp = _upload_i_zmapuj(admin_client, admin_user, csv, tworz_jednostki=False)

    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    assert not imp.jednostki_do_decyzji.exists()
    assert not imp.tytuly_do_decyzji.exists()

    # Import osób (pelny) rusza od razu z Kroku 2, bez zapisu struktury.
    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    admin_client.post(url_zatw, {"zakres": "pelny"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY


@pytest.mark.django_db
def test_jednostka_do_utworzenia_zostaje_w_kroku1(admin_client, admin_user):
    """Gdy w pliku jest jednostka NIEobecna w bazie (do utworzenia) — analiza NIE
    przeskakuje: zostaje Krok 1 (``przeanalizowany``) i pełny dwustopniowy commit
    (zakres=jednostki → ``struktura_zintegrowana`` → zakres=pelny →
    ``zintegrowany``)."""
    # Tytuł „dr" w bazie → twarde dopasowanie tytułu (zero decyzji o tytule),
    # więc jedynym powodem pozostania w Kroku 1 jest jednostka do utworzenia.
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    # autor pod „dr Jan Nowak" — żeby wiersz się zmatchował (nie wpływa na stan).
    baker.make(Autor, nazwisko="Nowak", imiona="Jan")

    csv = b"Osoba;Nazwa jednostki\ndr Jan Nowak;Nieistniejaca Katedra XYZ\n"
    imp = _upload_i_zmapuj(admin_client, admin_user, csv, tworz_jednostki=True)

    # jest jednostka do utworzenia → Krok 1; tytuł nie generuje decyzji
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    assert imp.jednostki_do_decyzji.exists()
    assert not imp.tytuly_do_decyzji.exists()

    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    # Krok 1: zapis struktury (zakres=jednostki) — dozwolony TYLKO z podglądu
    # (przeanalizowany). Że przechodzi, dowodzi, że analiza NIE przeskoczyła
    # tego stanu. (Materializacja konkretnej jednostki wymaga akceptacji decyzji
    # na ekranie „Zweryfikuj jednostki" — to inny flow, pokryty osobno.)
    admin_client.post(url_zatw, {"zakres": "jednostki"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA

    # Krok 2: import osób.
    admin_client.post(url_zatw, {"zakres": "pelny"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
