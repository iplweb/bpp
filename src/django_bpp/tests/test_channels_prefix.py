"""Tests for the channel-layer prefix resolver.

The resolver is the single source of truth that keeps the Daphne subprocess
(via ``CHANNEL_LAYERS``) and the test-side subscription poller agreeing on the
``channels_redis`` key prefix. See ``django_bpp.channels_prefix``.
"""

from django_bpp.channels_prefix import (
    DEFAULT_CHANNELS_PREFIX,
    get_channels_prefix,
)


def test_default_prefix_when_no_xdist_and_no_override(monkeypatch):
    """Production / single-process: the channels_redis default ``asgi``."""
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.delenv("DJANGO_BPP_CHANNELS_PREFIX", raising=False)
    assert get_channels_prefix() == DEFAULT_CHANNELS_PREFIX == "asgi"


def test_per_worker_prefix_under_xdist(monkeypatch):
    """Each xdist worker gets an isolated ``asgi-test-<worker>`` namespace."""
    monkeypatch.delenv("DJANGO_BPP_CHANNELS_PREFIX", raising=False)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw8")
    assert get_channels_prefix() == "asgi-test-gw8"


def test_explicit_override_wins_over_xdist(monkeypatch):
    """An explicit override takes precedence even under xdist."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    monkeypatch.setenv("DJANGO_BPP_CHANNELS_PREFIX", "custom-ns")
    assert get_channels_prefix() == "custom-ns"


def test_two_workers_get_distinct_prefixes(monkeypatch):
    """The whole point: different workers must not collide."""
    monkeypatch.delenv("DJANGO_BPP_CHANNELS_PREFIX", raising=False)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    first = get_channels_prefix()
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
    second = get_channels_prefix()
    assert first != second
