"""Faza integracji: walidacja niezmienników dat zatrudnienia (uwaga reviewera #4).

``Autor_Jednostka.clean()`` waliduje relację ``rozpoczal_prace`` < ``zakonczyl_prace``,
ale ``Model.save()`` NIE woła ``clean()`` — a integracja zapisuje przez zwykłe
``aj.save()``. Bez guardu na ścieżce integracji odwrócony zakres z XLS trafia do
bazy. Guard MUSI odrzucić taki wiersz (``BPPDatabaseError``) zanim cokolwiek
zapisze.
"""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_common.exceptions import BPPDatabaseError
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_odrzuca_odwrocony_zakres_dat(autor_jednostka_fixture):
    """Data rozpoczęcia >= data zakończenia → BPPDatabaseError, zero zapisu."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        zakonczyl_prace=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane={
            "data_zatrudnienia": "2026-12-31",
            "data_końca_zatrudnienia": "2026-01-01",
        },
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
    )

    with pytest.raises(BPPDatabaseError):
        integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    # Odwrócony zakres NIE został zapisany (transakcja per-wiersz wycofana).
    assert aj.rozpoczal_prace is None
    assert aj.zakonczyl_prace is None
