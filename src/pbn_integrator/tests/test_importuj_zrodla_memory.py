"""Memory-footprint regression tests for ``importuj_zrodla``.

The source import used to materialize *every* active ``Journal`` (each
carrying a potentially large ``versions`` JSON blob) into one Python list
and then capture each object twice inside the ``ThreadPoolExecutor``
futures dict. Peak memory scaled with the whole journal table.

The fix mirrors the already-memory-safe ``source_scoring_import``: gather
only primary keys up front and load each full ``Journal`` lazily inside the
worker thread, where it is garbage-collected right after processing. These
tests lock in that contract:

1. the thread worker accepts a journal *id* and loads the object itself;
2. ``importuj_zrodla`` dispatches lightweight *ids* to the pool, never the
   heavy ``Journal`` instances.
"""

import pytest
from model_bakery import baker

from bpp.models import Rodzaj_Zrodla, Zrodlo
from pbn_api.models import Journal


def _make_active_journal(title="Testowe czasopismo"):
    """Bake an ACTIVE PBN Journal with a usable ``current_version``."""
    return baker.make(
        Journal,
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {
                    "title": title,
                    "issn": "1234-5678",
                    "eissn": "",
                    "points": {},
                    "disciplines": [],
                },
            }
        ],
    )


@pytest.mark.django_db
def test_worker_accepts_id_and_loads_journal_lazily(monkeypatch):
    """The worker takes a journal *id* (str) and loads the object itself.

    Passing only the id is what keeps memory bounded: the heavy ``Journal``
    (with its ``versions`` JSON) is fetched inside the thread and freed right
    after, so at most ``max_workers`` journals are resident at once.
    """
    from pbn_integrator.importer import sources as sources_mod

    # The worker calls ``close_old_connections()`` because it is meant to run
    # in a pool thread; under a rolled-back test transaction that would close
    # the connection and hide the just-created row. Stub the pool hygiene out
    # so we can assert the lazy-load behavior we actually care about.
    monkeypatch.setattr(sources_mod, "close_old_connections", lambda: None)

    rodzaj_periodyk, _ = Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    journal = _make_active_journal()

    result = sources_mod._process_journal_thread_safe(journal.pk, rodzaj_periodyk, {})

    assert result["success"] is True, result
    assert Zrodlo.objects.filter(pbn_uid_id=journal.pk).exists()


@pytest.mark.django_db
def test_importuj_zrodla_dispatches_ids_not_objects(monkeypatch):
    """``importuj_zrodla`` must hand the pool ids, not ``Journal`` objects.

    Dispatching ids (32-char strings) instead of fully-hydrated model
    instances is the whole point of the memory fix.
    """
    from pbn_integrator.importer import sources as sources_mod

    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    _make_active_journal()

    captured = []

    def fake_worker(arg, rodzaj_periodyk, dyscypliny_cache):
        captured.append(arg)
        return {"success": True, "journal_id": arg, "error": None}

    monkeypatch.setattr(sources_mod, "_process_journal_thread_safe", fake_worker)

    sources_mod.importuj_zrodla(max_workers=2)

    assert captured, "worker was never invoked"
    assert all(isinstance(arg, str) for arg in captured), (
        f"expected journal ids (str), got: {[type(a).__name__ for a in captured]}"
    )
