from unittest import mock

import pytest

from ai_search import budget, translator


def _fake_response(query, error=None, usage=None):
    parsed = translator.DSLQuery(query=query, error=error)
    resp = mock.Mock()
    resp.parsed_output = parsed
    resp.stop_reason = "end_turn"
    u = usage or {}
    resp.usage = mock.Mock(
        input_tokens=u.get("input_tokens", 10),
        output_tokens=u.get("output_tokens", 5),
        cache_read_input_tokens=u.get("cache_read_tokens", 0),
        cache_creation_input_tokens=u.get("cache_write_tokens", 0),
    )
    return resp


@pytest.fixture(autouse=True)
def _schema(monkeypatch):
    monkeypatch.setattr(
        translator.schema_export,
        "schema_for_llm",
        lambda k: "SCHEMAT-TESTOWY",
    )


@pytest.mark.django_db
def test_valid_query_first_try():
    with mock.patch.object(
        translator, "_call_model", return_value=_fake_response("rok = 2024")
    ) as call:
        res = translator.translate("publikacje z 2024", "rekord")
    assert res.query == "rok = 2024"
    assert res.error is None
    assert res.attempts == 1
    assert call.call_count == 1


@pytest.mark.django_db
def test_null_query_passthrough():
    with mock.patch.object(
        translator,
        "_call_model",
        return_value=_fake_response(None, error="pytanie nieostre"),
    ):
        res = translator.translate("najlepsze prace", "rekord")
    assert res.query is None
    assert "nieostre" in res.error


@pytest.mark.django_db
def test_invalid_query_retries_then_succeeds():
    responses = [_fake_response('rok = "x'), _fake_response("rok = 2024")]
    with mock.patch.object(translator, "_call_model", side_effect=responses):
        res = translator.translate("prace z 2024", "rekord")
    assert res.query == "rok = 2024"
    assert res.retried is True
    assert res.attempts == 2


@pytest.mark.django_db
def test_invalid_after_retries_returns_error(settings):
    settings.BPP_AI_MAX_RETRIES = 1
    bad = _fake_response('rok = "x')
    with mock.patch.object(translator, "_call_model", return_value=bad) as call:
        res = translator.translate("prace z 2024", "rekord")
    assert res.query is None
    assert res.error  # komunikat błędu DjangoQL
    assert call.call_count == 2  # 1 + 1 retry


@pytest.mark.django_db
def test_max_retries_capped_at_two(settings):
    """Spec: default 1, cap 2 — niezależnie od ustawienia, maks. 1 + 2."""
    settings.BPP_AI_MAX_RETRIES = 10
    bad = _fake_response('rok = "x')
    with mock.patch.object(translator, "_call_model", return_value=bad) as call:
        res = translator.translate("prace z 2024", "rekord")
    assert res.query is None
    assert call.call_count == 3  # 1 + cap(2) retry, nie 1 + 10


@pytest.mark.django_db
def test_budget_check_blocks_retry_mid_loop():
    """budget_check zwraca ok=True przed 1. próbą, ok=False przed 2. —
    retry NIE może zostać wykonany, mimo że 1. próba dała niepoprawny query."""
    statuses = [
        budget.BudgetStatus(ok=True),
        budget.BudgetStatus(ok=False, reason="limit"),
    ]
    bad = _fake_response('rok = "x')
    with mock.patch.object(translator, "_call_model", return_value=bad) as call:
        res = translator.translate(
            "prace z 2024",
            "rekord",
            budget_check=mock.Mock(side_effect=statuses),
        )
    assert call.call_count == 1
    assert res.budget_blocked is True
    assert res.error == "limit"
    assert res.query is None


@pytest.mark.django_db
def test_budget_check_blocks_before_first_call():
    """budget_check już zablokowany przy pierwszej iteracji — _call_model
    nigdy nie zostaje wywołany."""
    with mock.patch.object(translator, "_call_model") as call:
        res = translator.translate(
            "prace z 2024",
            "rekord",
            budget_check=lambda: budget.BudgetStatus(ok=False, reason="limit"),
        )
    call.assert_not_called()
    assert res.budget_blocked is True
    assert res.error == "limit"
