"""E2E słowników stopień/stanowisko + e-mail: komórka złożona APOŻ → utworzenie
jednostki (Krok 1) → import osób ze stopniem/stanowiskiem/e-mailem (Krok 2).

Baseline testcontainers NIE zawiera struktur APOŻ — test sam przechodzi Krok 1
(tworzy jednostkę z komórki) i seeduje słowniki ``baker``iem. Izolację wyciekłej
pętli asyncio pod xdist zapewnia autouse-fixture z ``tests/conftest.py`` (obejmuje
też ten podkatalog). Wzorzec przebiegu: ``test_e2e_jednostki.py`` (patch
``otworz_zrodlo`` + jawne stany + ``MockProgress``)."""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj

KOMORKA = "RW-1/1 Zakład Kierowania Działaniami Ratowniczymi WIBiOL taktyka"

# Mapowanie nagłówków pliku → cele (jak po ekranie mapowania, Plan 2/3).
MAPOWANIE = {
    "komórka": "komórka_złożona",
    "nazwisko_imię": "nazwisko_imię",
    "email": "email",
    "stopień": "stopień_służbowy",
    "stanowisko_dyd": "stanowisko_dydaktyczne",
}


def _wiersz(nr, komorka, nazwisko_imie, email, stopien, stanowisko):
    return {
        "komórka": komorka,
        "nazwisko_imię": nazwisko_imie,
        "email": email,
        "stopień": stopien,
        "stanowisko_dyd": stanowisko,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": nr,
    }


def _run(imp, stan, zakres=None):
    imp.stan = stan
    if zakres is not None:
        imp.zakres_integracji = zakres
    imp.run(MockProgress(imp))
    imp.refresh_from_db()


@pytest.mark.django_db
def test_e2e_komorka_zlozona_stopnie_stanowiska_email(uczelnia):
    # --- Seed słowników (hard-match) + istniejący autor (no-overwrite e-mail) ---
    stopien = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    istniejacy = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", email="stary@example.com"
    )

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    imp.mapowanie_kolumn = MAPOWANIE
    imp.save(update_fields=["mapowanie_kolumn"])

    wiersze = [
        # NOWY autor — utworzony w Kroku 2; e-mail USTAWIONY.
        _wiersz(1, KOMORKA, "Anszczak Marcin", "marcin@example.com", "kpt.", "adiunkt"),
        # ISTNIEJĄCY autor — e-mail NIE nadpisany (no-overwrite §11).
        _wiersz(2, KOMORKA, "Kowalski Jan", "nowy@example.com", "kpt.", "adiunkt"),
    ]

    # --- KROK 1a: analiza (dry-run) ---
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = len(wiersze)
        MZ.return_value.data.return_value = iter(wiersze)
        analizuj(imp, MockProgress(imp))
    imp.refresh_from_db()

    # Jednostki z pliku nie ma w bazie → Krok 1 wymagany (nie auto-skip).
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    assert imp.jednostki_do_decyzji.exists()
    # nowy autor (brak dopasowania) — zaznacz „utwórz nowego" jak operator w UI.
    imp.importpracownikowrow_set.filter(autor__isnull=True).update(utworz_nowego=True)

    # --- KROK 1b: zapis STRUKTURY (jednostki + tytuły + stopnie/stanowiska) ---
    _run(
        imp,
        ImportPracownikow.STAN_ZATWIERDZONY,
        ImportPracownikow.ZAKRES_STRUKTURA,
    )
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    jednostka = Jednostka.objects.get(
        nazwa="Zakład Kierowania Działaniami Ratowniczymi"
    )
    assert jednostka.skrot == "RW-1/1"

    # --- KROK 2: import OSÓB (pełny) ---
    _run(
        imp,
        ImportPracownikow.STAN_ZATWIERDZONY,
        ImportPracownikow.ZAKRES_PELNY,
    )
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # Nowy autor: utworzony, e-mail + stopień USTAWIONE, AJ ze stanowiskiem.
    nowy = Autor.objects.get(nazwisko="Anszczak")
    assert nowy.email == "marcin@example.com"
    assert nowy.stopien_sluzbowy_id == stopien.pk
    aj_nowy = Autor_Jednostka.objects.get(autor=nowy, jednostka=jednostka)
    assert aj_nowy.stanowisko_id == stanow.pk

    # Istniejący autor: e-mail NIE nadpisany; stanowisko na AJ ustawione.
    istniejacy.refresh_from_db()
    assert istniejacy.email == "stary@example.com"  # no-overwrite §11
    aj_ist = Autor_Jednostka.objects.get(autor=istniejacy, jednostka=jednostka)
    assert aj_ist.stanowisko_id == stanow.pk
