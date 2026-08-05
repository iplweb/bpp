from datetime import timedelta

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_wykonuje_zaznaczone_odpiecie(yesterday):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka, podstawowe_miejsce_pracy=True)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == yesterday
    assert aj.podstawowe_miejsce_pracy is False
    assert odp.wykonane is True
    assert p.result_context["odpieto"] == 1


@pytest.mark.django_db
def test_commit_pomija_niezaznaczone_odpiecie():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=False
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace is None
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0


@pytest.mark.django_db
def test_commit_pomija_juz_zakonczone_recznie(today):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    wczesniej = today - timedelta(days=3)
    aj = baker.make(Autor_Jednostka, zakonczyl_prace=wczesniej)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == wczesniej
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0


@pytest.mark.django_db
def test_commit_pomija_odpiecie_pary_z_pliku():
    """G1: odpięcie zmaterializowane w analizie (gdy wiersz miał autor=None),
    ale user rozstrzygnął potem wiersz na TĘ parę (autor_id, jednostka_id) —
    para jest teraz W PLIKU, więc re-check MUSI pominąć odpięcie: AJ NIETKNIĘTE
    (``zakonczyl_prace`` nadal None, ``podstawowe`` niezmienione),
    ``wykonane=False``, licznik ``odpieto=0``."""
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka, podstawowe_miejsce_pracy=True)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=aj.autor,
        jednostka=aj.jednostka,
        zmiany_potrzebne=False,
    )
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace is None
    assert aj.podstawowe_miejsce_pracy is True
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0
