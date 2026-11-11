"""Metryki liczone i pokazywane dla wybranego okresu ewaluacji."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa, Uczelnia
from ewaluacja_common.okres import okres_domyslny
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania
from ewaluacja_metryki.utils import (
    generuj_metryki,
    oblicz_metryki_dla_autora,
    rozstrzygnij_okres,
)

from .conftest import wybierz_okres

PUSTE_SLOTY = (Decimal("0"), [], Decimal("0"))


def _metryka(okres, autor, dyscyplina, uczelnia, punkty):
    return baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        uczelnia=uczelnia,
        okres=okres,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal(punkty),
        slot_wszystkie=Decimal("2.0"),
        punkty_wszystkie=Decimal(punkty),
    )


@pytest.fixture
def dwie_metryki(okres_2022, okres_2026):
    uczelnia = baker.make(Uczelnia)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka", kod="9.999")
    m2022 = _metryka(okres_2022, autor, dyscyplina, uczelnia, "100")
    m2026 = _metryka(okres_2026, autor, dyscyplina, uczelnia, "200")
    return m2022, m2026


def test_rozstrzygnij_okres_wg_lat(okres_2022):
    okres, rok_min, rok_max = rozstrzygnij_okres(rok_min=2023, rok_max=2024)
    assert okres == okres_2022
    assert (rok_min, rok_max) == (2023, 2024)


def test_rozstrzygnij_okres_z_okresu(okres_2026):
    okres, rok_min, rok_max = rozstrzygnij_okres(okres_2026.pk)
    assert okres == okres_2026
    assert (rok_min, rok_max) == (2026, 2030)


@pytest.mark.django_db
def test_rozstrzygnij_okres_brak_okresu_dla_lat():
    with pytest.raises(ValueError):
        rozstrzygnij_okres(rok_min=1990, rok_max=1993)


def test_rozstrzygnij_okres_domyslny(okres_2022, okres_2026):
    okres, rok_min, rok_max = rozstrzygnij_okres()
    assert okres == okres_domyslny()
    assert (rok_min, rok_max) == (okres.rok_od, okres.rok_do)


def test_metryki_dwoch_okresow_wspolistnieja(okres_2022, okres_2026):
    uczelnia = baker.make(Uczelnia)
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    with patch.object(Autor, "zbieraj_sloty", return_value=PUSTE_SLOTY):
        for okres in (okres_2022, okres_2026):
            oblicz_metryki_dla_autora(
                autor,
                dyscyplina,
                uczelnia,
                okres=okres,
                slot_maksymalny=Decimal("4"),
            )
        # Ponowne przeliczenie jednego okresu nie rusza drugiego.
        oblicz_metryki_dla_autora(
            autor, dyscyplina, uczelnia, okres=okres_2026, slot_maksymalny=Decimal("4")
        )

    metryki = MetrykaAutora.objects.filter(autor=autor)
    assert metryki.count() == 2
    assert {(m.okres_id, m.rok_min, m.rok_max) for m in metryki} == {
        (okres_2022.pk, 2022, 2025),
        (okres_2026.pk, 2026, 2030),
    }


def test_generuj_metryki_nadpisz_tylko_w_okresie(
    okres_2022, okres_2026, rodzaj_autora_n
):
    uczelnia = baker.make(Uczelnia)
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    stara = _metryka(okres_2022, autor, dyscyplina, uczelnia, "100")

    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        uczelnia=uczelnia,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=rodzaj_autora_n,
        rok=2027,
    )

    with patch.object(Autor, "zbieraj_sloty", return_value=PUSTE_SLOTY):
        wynik = generuj_metryki(
            nadpisz=True, rodzaje_autora=["N"], uczelnia=uczelnia, okres=okres_2026
        )

    assert wynik["processed"] == 1
    assert MetrykaAutora.objects.filter(pk=stara.pk).exists()
    nowa = MetrykaAutora.objects.get(autor=autor, okres=okres_2026)
    assert (nowa.rok_min, nowa.rok_max) == (2026, 2030)


@pytest.mark.parametrize("ktory", [0, 1])
def test_lista_pokazuje_tylko_wybrany_okres(admin_user, client, dwie_metryki, ktory):
    wybrana = dwie_metryki[ktory]
    inna = dwie_metryki[1 - ktory]
    client.force_login(admin_user)
    wybierz_okres(client, wybrana.okres)

    response = client.get(reverse("ewaluacja_metryki:lista"))

    assert response.status_code == 200
    metryki = list(response.context["metryki"])
    assert wybrana in metryki
    assert inna not in metryki
    assert response.context["statystyki"]["liczba_wierszy"] == 1


def test_lista_bez_wyboru_pokazuje_okres_domyslny(admin_user, client, dwie_metryki):
    client.force_login(admin_user)

    response = client.get(reverse("ewaluacja_metryki:lista"))

    assert response.status_code == 200
    okresy = {m.okres_id for m in response.context["metryki"]}
    assert okresy == {okres_domyslny().pk}


@pytest.mark.parametrize("ktory", [0, 1])
def test_szczegoly_dla_wybranego_okresu(admin_user, client, dwie_metryki, ktory):
    wybrana = dwie_metryki[ktory]
    client.force_login(admin_user)
    wybierz_okres(client, wybrana.okres)

    response = client.get(wybrana.get_absolute_url())

    assert response.status_code == 200
    assert response.context["metryka"] == wybrana


@pytest.mark.parametrize("ktory", [0, 1])
def test_statystyki_dla_wybranego_okresu(admin_user, client, dwie_metryki, ktory):
    wybrana = dwie_metryki[ktory]
    client.force_login(admin_user)
    wybierz_okres(client, wybrana.okres)

    response = client.get(reverse("ewaluacja_metryki:statystyki"))

    assert response.status_code == 200
    assert response.context["statystyki_globalne"]["liczba_wierszy"] == 1
    assert list(response.context["top_autorzy"]) == [wybrana]


@pytest.mark.parametrize("ktory", [0, 1])
def test_eksport_listy_dla_wybranego_okresu(admin_user, client, dwie_metryki, ktory):
    from io import BytesIO

    from openpyxl import load_workbook

    wybrana = dwie_metryki[ktory]
    client.force_login(admin_user)
    wybierz_okres(client, wybrana.okres)

    response = client.get(reverse("ewaluacja_metryki:export_lista_xlsx"))

    assert response.status_code == 200
    ws = load_workbook(BytesIO(response.content)).active
    wartosci = [c for row in ws.iter_rows(values_only=True) for c in row]
    assert sum(1 for c in wartosci if c and "Kowalski" in str(c)) == 1
    assert wybrana.rok_min in wartosci
    assert dwie_metryki[1 - ktory].rok_min not in wartosci


def test_generowanie_dla_wybranego_okresu(admin_user, client, okres_2022, okres_2026):
    baker.make(Uczelnia)
    client.force_login(admin_user)
    wybierz_okres(client, okres_2022)

    with patch(
        "ewaluacja_metryki.views.generation.generuj_metryki_task_parallel"
    ) as mock_task:
        mock_task.delay.return_value = MagicMock(id="test-task-id")
        response = client.post(
            reverse("ewaluacja_metryki:uruchom_generowanie"),
            {"minimalny_pk": 0.01, "nadpisz": "on"},
        )

    assert response.status_code == 302
    kwargs = mock_task.delay.call_args.kwargs
    assert kwargs["okres_pk"] == okres_2022.pk
    assert (kwargs["rok_min"], kwargs["rok_max"]) == (2022, 2025)
    status = StatusGenerowania.objects.get(task_id="test-task-id")
    assert status.okres == okres_2022


@pytest.mark.parametrize("rok,rok_od", [(2023, 2022), (2027, 2026)])
def test_przeliczenie_publikacji_w_okresie_jej_roku(
    okres_2022, okres_2026, rok, rok_od
):
    from types import SimpleNamespace

    from ewaluacja_metryki.utils import _okres_dla_publikacji

    okres, rok_min, rok_max = _okres_dla_publikacji(
        SimpleNamespace(rok=rok), None, None, None
    )
    assert okres.rok_od == rok_od
    assert (rok_min, rok_max) == (okres.rok_od, okres.rok_do)
