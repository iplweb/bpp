"""Testy pomocnika retry na deadlocki denorm (``bpp.demo_data.db``)."""

import pytest
from django.db import IntegrityError, OperationalError

from bpp.demo_data.db import bulk_create_retry, retry_write


class _FakeManager:
    """Manager, który pada `fails` pierwszych razy wyjątkiem `exc`, potem OK."""

    def __init__(self, exc, fails):
        self.exc = exc
        self.fails = fails
        self.calls = 0

    def bulk_create(self, objs, **kwargs):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return objs


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Zerujemy backoff, żeby test był natychmiastowy."""
    import denorm.retry

    monkeypatch.setattr(denorm.retry.time, "sleep", lambda *a, **k: None)


def test_bulk_create_retry_ponawia_na_deadlocku():
    # Komunikat 'deadlock detected' → is_retryable (fallback po treści).
    mgr = _FakeManager(OperationalError("deadlock detected"), fails=2)
    result = bulk_create_retry(mgr, ["a", "b"])
    assert result == ["a", "b"]
    assert mgr.calls == 3  # 2 nieudane + 1 udana


def test_bulk_create_retry_NIE_ponawia_integrity_error():
    """KLUCZOWE: retry nie może maskować naruszeń unique (IntegrityError).

    Gdyby ponawiał, ukryłby np. duplikaty nazw Wydział/Jednostka zamiast je
    zgłosić."""
    mgr = _FakeManager(IntegrityError("duplicate key value"), fails=1)
    with pytest.raises(IntegrityError):
        bulk_create_retry(mgr, ["a"])
    assert mgr.calls == 1  # brak ponowienia


def test_bulk_create_retry_poddaje_sie_po_wyczerpaniu_prob():
    # Deadlock w kółko → po max_retries (5) i tak podnosi wyjątek.
    mgr = _FakeManager(OperationalError("deadlock detected"), fails=999)
    with pytest.raises(OperationalError):
        bulk_create_retry(mgr, ["a"])
    assert mgr.calls == 6  # 1 pierwotna + 5 ponowień (DEFAULT_MAX_RETRIES)


def test_retry_write_ponawia_na_serialization_failure():
    calls = {"n": 0}

    def zapis():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("could not serialize access due to ...")
        return "ok"

    assert retry_write(zapis) == "ok"
    assert calls["n"] == 2
