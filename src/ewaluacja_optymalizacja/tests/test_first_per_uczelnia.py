"""Track 6 (audyt uczelnia): ``Uczelnia.objects.first()`` → uczelnia z requestu.

Widoki ``ewaluacja_optymalizacja`` wcześniej zgadywały „pierwszą-z-brzegu"
uczelnię (``Uczelnia.objects.first()``) niezależnie od hosta (uczelni)
z requestu. Po naprawie biorą uczelnię z requestu
(``uczelnia_dla_odczytu`` / ``get_for_request``), a komendy CLI stosują
single-or-fail (``--uczelnia`` albo ``CommandError`` przy >1 uczelni).

Testy poniżej dowodzą, że:
- widok READ (``discipline_swap_opportunities_list``) operuje na danych U2,
  a nie U1, gdy request jest scoped do U2,
- widok MUTUJĄCY/enqueue (``start_bulk_optimization``) tworzy/kasuje
  ``OptimizationRun`` dla U2, nie dla U1,
- komendy ``solve_uczelnia`` / ``solve_evaluation`` failują przy >1 uczelni
  bez ``--uczelnia`` i honorują flagę.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Uczelnia


def _make_request(uczelnia, user=None):
    """Lekki fake request z ``_uczelnia`` (jak ustawia SiteResolutionMiddleware)."""

    class FakeRequest:
        GET = {}
        session = {}

    req = FakeRequest()
    req._uczelnia = uczelnia
    req.user = user
    return req


def _make_swap_opportunity(uczelnia, dyscyplina, autor, **kwargs):
    from ewaluacja_optymalizacja.models import DisciplineSwapOpportunity

    defaults = dict(
        uczelnia=uczelnia,
        rekord_id=[1, 1],
        rekord_tytul="Praca",
        rekord_rok=2023,
        autor=autor,
        current_discipline=dyscyplina,
        target_discipline=dyscyplina,
        points_before="10.0000",
        points_after="20.0000",
        point_improvement="10.0000",
        makes_sense=True,
    )
    defaults.update(kwargs)
    return DisciplineSwapOpportunity.objects.create(**defaults)


@pytest.fixture
def dwie_uczelnie(db):
    u1 = baker.make(Uczelnia, skrot="U1", nazwa="Uczelnia U1")
    u2 = baker.make(Uczelnia, skrot="U2", nazwa="Uczelnia U2")
    return u1, u2


@pytest.mark.django_db
def test_swap_list_view_operuje_na_uczelni_z_requestu(dwie_uczelnie):
    """Widok READ filtruje DisciplineSwapOpportunity po uczelni z requestu (U2)."""
    from bpp.models import Dyscyplina_Naukowa
    from ewaluacja_optymalizacja.views.discipline_swap_list import (
        discipline_swap_opportunities_list,
    )

    u1, u2 = dwie_uczelnie
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    autor = baker.make("bpp.Autor")

    # 2 możliwości dla U1, 1 dla U2 — gdyby widok brał first()-of-arbitrary,
    # wziąłby U1 (utworzona pierwsza) i policzyłby 2 zamiast 1.
    _make_swap_opportunity(u1, dyscyplina, autor)
    _make_swap_opportunity(u1, dyscyplina, autor)
    _make_swap_opportunity(u2, dyscyplina, autor)

    su = baker.make("bpp.BppUser", is_superuser=True)
    request = _make_request(u2, user=su)

    captured = {}

    def fake_render(req, template, context):
        captured.update(context)
        from django.http import HttpResponse

        return HttpResponse("ok")

    with patch(
        "ewaluacja_optymalizacja.views.discipline_swap_list.render",
        side_effect=fake_render,
    ):
        discipline_swap_opportunities_list(request)

    assert captured["total_count"] == 1, (
        "Widok policzył możliwości spoza uczelni z requestu — "
        "first()-of-arbitrary zamiast U2."
    )


@pytest.mark.django_db
def test_bulk_optimization_kasuje_runy_uczelni_z_requestu(dwie_uczelnie):
    """Widok MUTUJĄCY/enqueue operuje na OptimizationRun uczelni z requestu (U2)."""
    from bpp.models import Dyscyplina_Naukowa
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
    from ewaluacja_optymalizacja.models import OptimizationRun
    from ewaluacja_optymalizacja.views.bulk_optimization import (
        start_bulk_optimization,
    )

    u1, u2 = dwie_uczelnie
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    # U2 ma raportowaną liczbę N, więc walidacja w widoku przejdzie.
    baker.make(
        LiczbaNDlaUczelni,
        uczelnia=u2,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=20,
    )

    # Stare runy dla obu uczelni — widok powinien skasować TYLKO U2.
    baker.make(OptimizationRun, uczelnia=u1, dyscyplina_naukowa=dyscyplina)
    baker.make(OptimizationRun, uczelnia=u2, dyscyplina_naukowa=dyscyplina)

    su = baker.make("bpp.BppUser", is_superuser=True)
    request = _make_request(u2, user=su)
    request.method = "POST"
    request.POST = {}

    # Zablokuj faktyczny enqueue zadania Celery (zwróć fake task z .id).
    class FakeTask:
        id = "fake-task-id"

    with patch(
        "ewaluacja_optymalizacja.views.bulk_optimization."
        "solve_all_reported_disciplines.delay",
        return_value=FakeTask(),
    ):
        start_bulk_optimization(request)

    assert not OptimizationRun.objects.filter(uczelnia=u2).exists(), (
        "Run U2 powinien zostać skasowany przed nową optymalizacją."
    )
    assert OptimizationRun.objects.filter(uczelnia=u1).exists(), (
        "Run U1 NIE może zostać ruszony — widok operował na first()-of-arbitrary."
    )


@pytest.mark.django_db
def test_browser_toggle_pin_enqueue_dla_uczelni_z_requestu(dwie_uczelnie):
    """``browser_toggle_pin`` (mutujący/enqueue) scope'uje przeliczanie do
    uczelni z requestu (U2) — NIE do pierwszej-z-brzegu (U1).

    Dowód: ``solve_all_reported_disciplines.delay`` dostaje ``U2.pk``, a
    ``StatusPrzegladarkaRecalc`` startuje dla U2. Gdyby widok używał
    ``uczelnia_dla_odczytu`` z honorowaniem ``?uczelnia=`` override albo
    ``get_default`` first()-of-arbitrary, mógłby trafić w U1.
    """
    from ewaluacja_optymalizacja.models import StatusPrzegladarkaRecalc
    from ewaluacja_optymalizacja.views.evaluation_browser.views import (
        browser_toggle_pin,
    )

    u1, u2 = dwie_uczelnie
    autor_rekord = baker.make("bpp.Wydawnictwo_Ciagle_Autor", przypieta=False)

    su = baker.make("bpp.BppUser", is_superuser=True)
    request = _make_request(u2, user=su)
    request.method = "POST"
    request.POST = {}

    class FakeTask:
        id = "fake-task-id"

    def fake_render(req, template, context):
        from django.http import HttpResponse

        return HttpResponse("ok")

    with (
        patch(
            "ewaluacja_optymalizacja.views.evaluation_browser.views."
            "solve_all_reported_disciplines.delay",
            return_value=FakeTask(),
        ) as mock_delay,
        patch(
            "ewaluacja_optymalizacja.views.evaluation_browser.views.render",
            side_effect=fake_render,
        ),
    ):
        browser_toggle_pin(request, "ciagle", autor_rekord.pk)

    mock_delay.assert_called_once_with(u2.pk)
    assert mock_delay.call_args.args != (u1.pk,), (
        "Przeliczanie poszło do U1 (first()-of-arbitrary) zamiast U2 z requestu."
    )

    status = StatusPrzegladarkaRecalc.get_or_create()
    assert status.uczelnia_id == u2.pk, (
        "StatusPrzegladarkaRecalc wystartował dla złej uczelni — "
        "mutacja nie była scoped do uczelni z requestu."
    )


@pytest.mark.django_db
def test_solve_uczelnia_command_failuje_przy_wielu_uczelniach(dwie_uczelnie):
    """``solve_uczelnia`` bez --uczelnia przy >1 uczelni → CommandError."""
    with pytest.raises(CommandError, match="więcej niż jedna uczelnia"):
        call_command("solve_uczelnia", stdout=StringIO())


@pytest.mark.django_db
def test_solve_uczelnia_command_honoruje_flage(dwie_uczelnie):
    """``solve_uczelnia --uczelnia <pk>`` używa wskazanej uczelni (bez błędu)."""
    u1, u2 = dwie_uczelnie
    out = StringIO()
    # Brak danych liczby N → solve_uczelnia nie przetworzy dyscyplin, ale
    # NIE może rzucić CommandError o wielu uczelniach — flaga rozstrzyga.
    call_command("solve_uczelnia", uczelnia=u2.pk, stdout=out)
    assert f"University: {u2}" in out.getvalue()


@pytest.mark.django_db
def test_solve_evaluation_command_failuje_przy_wielu_uczelniach(dwie_uczelnie):
    """``solve_evaluation`` bez --uczelnia przy >1 uczelni → CommandError."""
    with pytest.raises(CommandError, match="więcej niż jedna uczelnia"):
        call_command("solve_evaluation", "nauki medyczne", stdout=StringIO())
