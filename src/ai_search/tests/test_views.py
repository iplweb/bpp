from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse

from ai_search import translator
from ai_search.models import AISearchQuery


@pytest.fixture
def staff_client(client, django_user_model):
    u = django_user_model.objects.create_user(
        username="ed", password="x", is_staff=True, is_superuser=True
    )
    client.force_login(u)
    return client


@pytest.mark.django_db
def test_anonymous_denied(client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    r = client.get(reverse("ai_search:index"))
    assert r.status_code in (302, 403)


@pytest.mark.django_db
def test_get_form_visible_for_staff(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    r = staff_client.get(reverse("ai_search:index"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_post_success_redirects_to_zapytanie(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    res = translator.TranslationResult(
        query="rok = 2024", usage={"input_tokens": 10, "output_tokens": 5}, attempts=1
    )
    with (
        mock.patch("ai_search.views.translator.translate", return_value=res),
        mock.patch("ai_search.views.fx.usd_to_pln_rate", return_value=Decimal("4.1")),
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "publikacje z 2024"},
        )
    assert r.status_code == 302
    assert reverse("bpp:zapytanie") in r.url
    assert "query=rok" in r.url.replace("%20", " ") or "rok" in r.url
    log = AISearchQuery.objects.get()
    assert log.success is True
    assert log.cost_pln > 0


@pytest.mark.django_db
def test_post_blocked_by_budget(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_DAILY_BUDGET_PLN = "0"
    r = staff_client.post(
        reverse("ai_search:index"),
        {"model": "rekord", "pytanie": "cokolwiek"},
    )
    assert r.status_code == 200
    assert b"limit" in r.content.lower()
    assert AISearchQuery.objects.count() == 0


@pytest.mark.django_db
def test_post_budget_blocked_mid_retry_logs_cost_and_renders_message(
    staff_client, settings
):
    """Blok budżetu W TRAKCIE retry (po >=1 płatnej próbie) — w odróżnieniu
    od pre-checku (test_post_blocked_by_budget) — loguje poniesiony koszt
    i renderuje komunikat budżetowy."""
    settings.BPP_AI_SEARCH_ENABLED = True
    res = translator.TranslationResult(
        query=None,
        error="Dzienny limit kosztów AI został osiągnięty.",
        usage={"input_tokens": 10, "output_tokens": 5},
        attempts=1,
        budget_blocked=True,
    )
    with (
        mock.patch("ai_search.views.translator.translate", return_value=res),
        mock.patch("ai_search.views.fx.usd_to_pln_rate", return_value=Decimal("4.1")),
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "cokolwiek"},
        )
    assert r.status_code == 200
    assert "limit" in r.content.decode().lower()
    log = AISearchQuery.objects.get()
    assert log.success is False
    assert log.cost_pln > 0


@pytest.mark.django_db
def test_post_translate_raises_shows_friendly_error(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    with (
        mock.patch(
            "ai_search.views.translator.translate",
            side_effect=Exception("boom"),
        ),
        mock.patch("ai_search.views.rollbar.report_exc_info") as report,
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "cokolwiek"},
        )
    assert r.status_code == 200
    assert "chwilowo niedostępna" in r.content.decode()
    report.assert_called_once()
    assert AISearchQuery.objects.count() == 0


@pytest.mark.django_db
def test_post_pricing_keyerror_logs_zero_cost(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    res = translator.TranslationResult(
        query="rok = 2024", usage={"input_tokens": 10, "output_tokens": 5}, attempts=1
    )
    with (
        mock.patch("ai_search.views.translator.translate", return_value=res),
        mock.patch("ai_search.views.fx.usd_to_pln_rate", return_value=Decimal("4.1")),
        mock.patch(
            "ai_search.views.pricing.cost_usd_from_usage",
            side_effect=KeyError("nieznany-model"),
        ),
        mock.patch("ai_search.views.rollbar.report_exc_info") as report,
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "publikacje z 2024"},
        )
    assert r.status_code == 302
    report.assert_called_once()
    log = AISearchQuery.objects.get()
    assert log.success is True
    assert log.cost_usd == Decimal("0")
    assert log.cost_pln == Decimal("0")


@pytest.mark.django_db
def test_post_openai_backend_skips_budget_and_logs_zero_cost(staff_client, settings):
    """Backend lokalny (openai-compatible): brak pre-checku budżetu, brak
    `budget_check` przekazanego do translatora, koszt/kurs zawsze 0 — bez
    wołania pricing/fx (nieistotny cennik dla modelu lokalnego)."""
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_DAILY_BUDGET_PLN = "0"  # budżet "wyczerpany" — ma być ignorowany
    res = translator.TranslationResult(
        query="rok = 2024", usage={"input_tokens": 10, "output_tokens": 5}, attempts=1
    )
    with (
        mock.patch(
            "ai_search.views.translator.translate", return_value=res
        ) as translate_mock,
        mock.patch("ai_search.views.pricing.cost_usd_from_usage") as pricing_mock,
        mock.patch("ai_search.views.fx.usd_to_pln_rate") as fx_mock,
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "publikacje z 2024"},
        )
    assert r.status_code == 302
    assert reverse("bpp:zapytanie") in r.url
    assert translate_mock.call_args.kwargs["budget_check"] is None
    pricing_mock.assert_not_called()
    fx_mock.assert_not_called()
    log = AISearchQuery.objects.get()
    assert log.success is True
    assert log.cost_usd == Decimal("0")
    assert log.fx_rate == Decimal("0")
    assert log.cost_pln == Decimal("0")


@pytest.mark.django_db
def test_post_miscased_backend_is_treated_as_anthropic_budget_applies(
    staff_client, settings
):
    """Literówka w BPP_AI_BACKEND (np. 'Anthropic' zamiast 'anthropic') NIE
    MOŻE ominąć budżetu — to jest sedno FIX 1: `get_backend()` i widok mają
    być zgodne, więc dla dowolnej wartości ≠ dokładnie 'openai' widok musi
    zablokować zapytanie pre-checkiem budżetu, dokładnie jak dla
    'anthropic' (patrz test_post_blocked_by_budget)."""
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "Anthropic"  # zła wielkość liter - literówka
    settings.BPP_AI_DAILY_BUDGET_PLN = "0"  # budżet "wyczerpany"
    r = staff_client.post(
        reverse("ai_search:index"),
        {"model": "rekord", "pytanie": "cokolwiek"},
    )
    assert r.status_code == 200
    assert "limit" in r.content.decode().lower()
    assert AISearchQuery.objects.count() == 0


@pytest.mark.django_db
def test_post_miscased_backend_logs_real_cost_not_zero(staff_client, settings):
    """Dla tej samej literówki, gdy budżet NIE jest wyczerpany: koszt/kurs
    muszą być liczone tak jak dla 'anthropic' (niezerowe), a nie potraktowane
    jak darmowy backend lokalny (por. test_post_openai_backend_skips_budget_
    and_logs_zero_cost, gdzie cost_pln == 0)."""
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "Anthropic"  # zła wielkość liter - literówka
    res = translator.TranslationResult(
        query="rok = 2024", usage={"input_tokens": 10, "output_tokens": 5}, attempts=1
    )
    with (
        mock.patch("ai_search.views.translator.translate", return_value=res) as tr,
        mock.patch("ai_search.views.fx.usd_to_pln_rate", return_value=Decimal("4.1")),
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "publikacje z 2024"},
        )
    assert r.status_code == 302
    assert tr.call_args.kwargs["budget_check"] is not None
    log = AISearchQuery.objects.get()
    assert log.success is True
    assert log.cost_pln > 0


@pytest.mark.django_db
def test_post_null_query_shows_error(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    res = translator.TranslationResult(
        query=None, error="pytanie nieostre", usage={"input_tokens": 5}, attempts=1
    )
    with (
        mock.patch("ai_search.views.translator.translate", return_value=res),
        mock.patch("ai_search.views.fx.usd_to_pln_rate", return_value=Decimal("4.1")),
    ):
        r = staff_client.post(
            reverse("ai_search:index"),
            {"model": "rekord", "pytanie": "najlepsze prace"},
        )
    assert r.status_code == 200
    assert "nieostre" in r.content.decode()
    assert AISearchQuery.objects.get().success is False
