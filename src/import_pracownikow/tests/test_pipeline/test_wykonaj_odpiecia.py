"""Jednostkowe testy `_wykonaj_odpiecia` — zakończenie zatrudnienia dla
zaznaczonych odpięć (§9) oraz ochrona już ustawionej daty końca.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie
from import_pracownikow.pipeline.integrate import _wykonaj_odpiecia


@pytest.mark.django_db
def test_wykonaj_odpiecia_konczy_zatrudnienie_bez_daty_konca():
    """Ścieżka główna: AJ bez daty końca jest odpinany — koniec = wczoraj,
    podstawowe miejsce = False, odpięcie oznaczone jako wykonane."""
    today = timezone.now().date()
    aj = baker.make(
        Autor_Jednostka,
        autor=baker.make(Autor),
        jednostka=baker.make(Jednostka),
        zakonczyl_prace=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )

    odpieto = _wykonaj_odpiecia(imp)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == today - timedelta(days=1)
    assert aj.podstawowe_miejsce_pracy is False
    assert odp.wykonane is True
    assert odpieto == 1


@pytest.mark.django_db
def test_wykonaj_odpiecia_nie_nadpisuje_przyszlej_daty_konca():
    """Odpięcie NIE nadpisuje USTAWIONEJ daty końca — także PRZYSZŁEJ
    (planowanej). Po zdjęciu zakazu dat w przyszłości (mig 0469) guard
    `zakonczyl_prace <= today` przepuszczał przyszłą datę do nadpisania
    wczorajszą, kasując świadomie zaplanowany koniec umowy. Ustawiona data
    końca (przeszła czy przyszła) = decyzja człowieka → pomijamy."""
    przyszlosc = timezone.now().date() + timedelta(days=365)
    aj = baker.make(
        Autor_Jednostka,
        autor=baker.make(Autor),
        jednostka=baker.make(Jednostka),
        zakonczyl_prace=przyszlosc,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )

    odpieto = _wykonaj_odpiecia(imp)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == przyszlosc  # NIE nadpisane wczorajszą datą
    assert odp.wykonane is False
    assert odpieto == 0
