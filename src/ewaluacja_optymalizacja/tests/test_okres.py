"""Optymalizacja liczona dla wybranego okresu ewaluacji (nie na sztywno
2022–2025)."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_common.okres import KLUCZ_SESJI
from ewaluacja_optymalizacja.models import OptimizationRun
from ewaluacja_optymalizacja.okres import limity_slotow_autora


def _wybierz_okres(client, okres):
    sesja = client.session
    sesja[KLUCZ_SESJI] = okres.pk
    sesja.save()


@pytest.fixture
def runy_dwoch_okresow(okres_2022, okres_2026):
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    run_2022 = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        okres=okres_2022,
        status="completed",
    )
    run_2026 = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        okres=okres_2026,
        status="completed",
    )
    return run_2022, run_2026


@pytest.mark.django_db
def test_okres_domyslny_runa(okres_2022):
    """Run utworzony bez jawnego okresu dostaje okres domyślny."""
    run = baker.make(OptimizationRun)
    assert run.okres == okres_2022


@pytest.mark.django_db
def test_run_list_pokazuje_runy_wybranego_okresu(
    admin_client, runy_dwoch_okresow, okres_2026
):
    run_2022, run_2026 = runy_dwoch_okresow
    url = reverse("ewaluacja_optymalizacja:run-list")

    # Bez wyboru w sesji: okres domyślny (w testach 2022–2025)
    runs = list(admin_client.get(url).context["runs"])
    assert runs == [run_2022]

    _wybierz_okres(admin_client, okres_2026)
    runs = list(admin_client.get(url).context["runs"])
    assert runs == [run_2026]


@pytest.mark.django_db
def test_index_pokazuje_runy_wybranego_okresu(
    admin_client, uczelnia, runy_dwoch_okresow, okres_2026
):
    run_2022, run_2026 = runy_dwoch_okresow
    url = reverse("ewaluacja_optymalizacja:index")

    res = admin_client.get(url)
    assert [r.pk for r in res.context["optimization_runs"]] == [run_2022.pk]

    _wybierz_okres(admin_client, okres_2026)
    res = admin_client.get(url)
    assert [r.pk for r in res.context["optimization_runs"]] == [run_2026.pk]
    assert res.context["okres"] == okres_2026


@pytest.mark.django_db
def test_discipline_comparison_wg_okresu(admin_client, runy_dwoch_okresow, okres_2026):
    run_2022, run_2026 = runy_dwoch_okresow
    url = reverse("ewaluacja_optymalizacja:discipline-comparison")

    stats = admin_client.get(url).context["discipline_stats"]
    assert [s["run_id"] for s in stats] == [run_2022.pk]

    _wybierz_okres(admin_client, okres_2026)
    stats = admin_client.get(url).context["discipline_stats"]
    assert [s["run_id"] for s in stats] == [run_2026.pk]


def test_limity_slotow_skaluja_sie_z_dlugoscia_okresu():
    okres_4 = MagicMock(liczba_lat=4)
    okres_5 = MagicMock(liczba_lat=5)
    assert limity_slotow_autora(okres_4) == (4.0, 2.0)
    assert limity_slotow_autora(okres_5) == (5.0, 2.5)


@pytest.mark.django_db
def test_generate_pub_data_uzywa_lat_okresu(okres_2026):
    from ewaluacja_optymalizacja.core.data_loader import generate_pub_data

    baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    with patch(
        "ewaluacja_optymalizacja.core.data_loader.Cache_Punktacja_Autora_Query"
    ) as cache:
        generate_pub_data("Okresowa", okres=okres_2026)

    kwargs = cache.objects.filter.call_args.kwargs
    assert kwargs["rekord__rok__gte"] == 2026
    assert kwargs["rekord__rok__lte"] == 2030


@pytest.mark.django_db
def test_load_author_slot_limits_domyslne_wg_okresu(okres_2022, okres_2026):
    from ewaluacja_optymalizacja.core.data_loader import load_author_slot_limits

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make("bpp.Autor")

    def log(*args, **kwargs):
        return None

    limity = load_author_slot_limits([autor.pk], dyscyplina, log, okres=okres_2022)
    assert limity[autor.pk] == {"total": 4.0, "mono": 2.0}

    limity = load_author_slot_limits([autor.pk], dyscyplina, log, okres=okres_2026)
    assert limity[autor.pk] == {"total": 5.0, "mono": 2.5}


@pytest.mark.django_db
def test_solve_single_discipline_task_kasuje_tylko_runy_swojego_okresu(
    uczelnia, runy_dwoch_okresow, okres_2026
):
    from ewaluacja_optymalizacja.core import _empty_results
    from ewaluacja_optymalizacja.tasks import solve_single_discipline_task

    run_2022, run_2026 = runy_dwoch_okresow
    dyscyplina = run_2022.dyscyplina_naukowa

    with patch(
        "ewaluacja_optymalizacja.core.solve_discipline",
        return_value=_empty_results(dyscyplina.nazwa),
    ) as solve:
        wynik = solve_single_discipline_task(
            uczelnia.pk, dyscyplina.pk, 12.0, okres_pk=okres_2026.pk
        )

    assert solve.call_args.kwargs["okres"] == okres_2026
    assert wynik["status"] == "completed"
    # Run z 2022–2025 przetrwał, stary run 2026–2030 zastąpiony nowym
    assert OptimizationRun.objects.filter(pk=run_2022.pk).exists()
    assert not OptimizationRun.objects.filter(pk=run_2026.pk).exists()
    nowy = OptimizationRun.objects.get(pk=wynik["optimization_run_id"])
    assert nowy.okres == okres_2026


def _odpieta_praca(autor, dyscyplina, rok):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=rok,
        dyscyplina_naukowa=dyscyplina,
        subdyscyplina_naukowa=None,
    )
    return baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=baker.make(Wydawnictwo_Ciagle, rok=rok),
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        przypieta=False,
    )


@pytest.mark.django_db
def test_reset_all_pins_task_rusza_tylko_lata_okresu(uczelnia, okres_2026):
    from ewaluacja_optymalizacja.tasks import reset_all_pins_task

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make("bpp.Autor")
    w_okresie = _odpieta_praca(autor, dyscyplina, 2027)
    poza_okresem = _odpieta_praca(autor, dyscyplina, 2023)

    with patch("ewaluacja_optymalizacja.tasks.reset_pins._wait_for_denorm"):
        wynik = reset_all_pins_task.apply(
            args=(uczelnia.pk,), kwargs={"okres_pk": okres_2026.pk}
        ).result

    w_okresie.refresh_from_db()
    poza_okresem.refresh_from_db()
    assert w_okresie.przypieta is True
    assert poza_okresem.przypieta is False
    assert wynik["total_reset"] == 1


@pytest.mark.django_db
def test_reset_discipline_pins_task_rusza_tylko_lata_okresu(
    uczelnia, admin_user, okres_2022
):
    from ewaluacja_optymalizacja.tasks import reset_discipline_pins_task

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make("bpp.Autor")
    w_okresie = _odpieta_praca(autor, dyscyplina, 2024)
    poza_okresem = _odpieta_praca(autor, dyscyplina, 2026)

    with (
        patch("ewaluacja_optymalizacja.tasks.reset_pins._wait_for_denorm"),
        patch("denorm.tasks.flush_via_queue"),
    ):
        reset_discipline_pins_task.apply(
            args=(uczelnia.pk, dyscyplina.pk, admin_user.pk),
            kwargs={"okres_pk": okres_2022.pk},
        )

    w_okresie.refresh_from_db()
    poza_okresem.refresh_from_db()
    assert w_okresie.przypieta is True
    assert poza_okresem.przypieta is False


@pytest.mark.django_db
def test_reset_all_pins_widok_przekazuje_okres_z_sesji(
    admin_client, uczelnia, okres_2026
):
    _wybierz_okres(admin_client, okres_2026)
    with (
        patch("ewaluacja_optymalizacja.tasks.reset_all_pins_task") as task,
        patch(
            "ewaluacja_optymalizacja.views.pins.Uczelnia.objects.get_for_request",
            return_value=uczelnia,
        ),
    ):
        task.delay.return_value = MagicMock(id="abc")
        admin_client.get(reverse("ewaluacja_optymalizacja:reset-all-pins"))

    task.delay.assert_called_once_with(uczelnia.pk, okres_pk=okres_2026.pk)
