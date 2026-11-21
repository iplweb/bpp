"""E2E: create_demo_data --polon-plik → import z POLON (2022–2025) → liczba N.

Plik ma dać liczbę N >= 12 w trzech dyscyplinach i < 12 w czwartej
(„nauki teologiczne" — dyscyplina nieraportowana).
"""

from decimal import Decimal

import pytest
from django.apps import apps
from django.core.files import File
from django.core.management import call_command
from django.db import connection
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.demo_data.default_dyscypliny import seed_default_dyscypliny
from bpp.demo_data.generators.polon import (
    DOMYSLNE_DYSCYPLINY,
    DYSCYPLINA_SPOZA_SLOWNIKA,
    OSOBA_SPOZA_BPP,
)
from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import Autor_Dyscyplina, Uczelnia
from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_liczba_n.utils import (
    oblicz_dyscypliny_nieraportowane,
    oblicz_liczby_n_dla_okresu,
)
from import_polon.core.import_polon import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

LATA = (2022, 2023, 2024, 2025)


@pytest.fixture
def slowniki(db):
    seed_default_dyscypliny()
    for label, _ in REQUIRED_DICTIONARIES:
        model = apps.get_model(*label.split("."))
        if not model.objects.exists():
            baker.make(model)


def _importuj(plik, uczelnia, rok):
    import_model = baker.make(
        ImportPlikuPolon,
        rok=rok,
        uczelnia=uczelnia,
        zapisz_zmiany_do_bazy=True,
        ukryj_niezmatchowanych_autorow=False,
        ignoruj_miejsce_pracy=False,
    )
    with open(plik, "rb") as f:
        import_model.plik.save(plik.name, File(f))
    wynik = analyze_file_import_polon(
        str(plik), import_model, MockProgress(import_model)
    )
    return import_model, wynik["statystyki"]


# Słownik z baseline; test transakcyjny na tym samym workerze go wymiata.
@pytest.mark.usefixtures(
    "rodzaj_autora_n", "rodzaj_autora_b", "rodzaj_autora_d", "rodzaj_autora_z"
)
@pytest.mark.django_db
def test_e2e_plik_polon_import_i_liczba_n(slowniki, tmp_path):
    plik = tmp_path / "polon.xlsx"
    call_command(
        "create_demo_data",
        "--autorow=150",
        "--wydzialow=2",
        "--jednostek-na-wydzial=3",
        "--ile-ciaglych=5",
        "--ile-zwartych=5",
        "--zrodel=3",
        "--wydawcow=2",
        "--od-roku=2022",
        "--do-roku=2025",
        "--seed=42",
        f"--manifest-out={tmp_path / 'm.json'}",
        "--batch-size=50",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
        f"--polon-plik={plik}",
    )
    assert plik.exists()
    uczelnia = Uczelnia.objects.get()

    for rok in LATA:
        import_model, stat = _importuj(plik, uczelnia, rok)
        wiersze = WierszImportuPlikuPolon.objects.filter(parent=import_model)
        assert wiersze.count() == stat["wierszy_w_pliku"]

        # Dokładnie cztery celowo błędne wiersze, po jednym z rodzaju.
        assert stat["odrzuconych_zatrudnienie"] == 1
        assert stat["z_bledem"] == 3
        bledy = {w.rezultat for w in wiersze.exclude(autor=None)} | {
            w.rezultat
            for w in wiersze.filter(autor=None)
            if w.dane_z_xls["NAZWISKO"] == OSOBA_SPOZA_BPP[1]
        }
        assert "Nie udało się dopasować autora" in bledy
        assert any("dopasować dyscypliny" in b for b in bledy)
        assert any("Wymiar etatu nie może być puste" in b for b in bledy)
        assert (
            wiersze.filter(
                dane_z_xls__DYSCYPLINA_N=DYSCYPLINA_SPOZA_SLOWNIKA,
                autor__isnull=False,
            ).count()
            == 1
        )
        # Reszta dopasowana i zapisana.
        assert stat["dopasowanych"] == stat["wierszy_w_pliku"] - 2

    # Rodzaje autorów ustawione z pliku: N dla OSWIADCZENIE_N=Tak.
    for rok in LATA:
        n = Autor_Dyscyplina.objects.filter(rok=rok, rodzaj_autora__skrot="N")
        assert n.count() > 40
        assert Autor_Dyscyplina.objects.filter(
            rok=rok, rodzaj_autora__skrot="B"
        ).exists()
        assert Autor_Dyscyplina.objects.filter(
            rok=rok, rodzaj_autora__skrot="Z"
        ).exists()

    # Okres jawnie: domyślny zależy od bieżącego roku (od 2026 → 2026–2030),
    # a plik POL-on pokrywa lata 2022–2025.
    okres = OkresEwaluacji.objects.get(rok_od=LATA[0])
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres)

    liczba_n = {
        o.dyscyplina_naukowa.nazwa: o.liczba_n
        for o in LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia, okres=okres)
    }
    for nazwa, cel in DOMYSLNE_DYSCYPLINY:
        if cel >= 12:
            assert liczba_n[nazwa] >= 12, (nazwa, liczba_n)
        else:
            assert Decimal("0") < liczba_n[nazwa] < 12, (nazwa, liczba_n)

    nieraportowane = oblicz_dyscypliny_nieraportowane(uczelnia, okres=okres)
    assert {nazwa for nazwa, _ in DOMYSLNE_DYSCYPLINY if nazwa in liczba_n} & set(
        LiczbaNDlaUczelni.objects.filter(
            okres=okres, dyscyplina_naukowa_id__in=nieraportowane
        ).values_list("dyscyplina_naukowa__nazwa", flat=True)
    ) == {"nauki teologiczne"}
