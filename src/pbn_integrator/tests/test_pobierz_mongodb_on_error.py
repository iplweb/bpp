"""Knob ``on_error`` w ``pobierz_mongodb``: fail-fast (default) vs skip-and-continue.

Błąd dotyczy zapisu POJEDYNCZEGO rekordu do lokalnego lustra BPP (nie PBN).
``"raise"`` (default) zachowuje historyczne fail-fast; ``"skip"`` deleguje do
pakietowego ``download_to_model`` (log + licznik + kontynuacja).
"""

from unittest.mock import MagicMock

import pytest


def _fun_failing_on(bad_id):
    """Save-fun rzucający na elemencie o danym ``id``, resztę „zapisujący”."""
    saved = []

    def fun(elem, klass, client=None, **extra):
        if elem["id"] == bad_id:
            raise ValueError(f"boom {bad_id}")
        saved.append(elem["id"])

    fun.saved = saved
    return fun


def test_on_error_raise_jest_domyslny_fail_fast():
    """Default = fail-fast: pierwszy błąd przerywa batch, reszta nietknięta."""
    from pbn_integrator.utils.mongodb_ops import pobierz_mongodb

    elems = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    fun = _fun_failing_on("b")
    with pytest.raises(ValueError, match="boom b"):
        pobierz_mongodb(elems, MagicMock(), fun=fun, disable_progress_bar=True)
    # „c” (po zepsutym „b”) NIE zostało zapisane — batch przerwany.
    assert fun.saved == ["a"]


def test_on_error_skip_kontynuuje_i_liczy_bledy():
    """``skip`` = kontynuuj mimo błędu; zwraca DownloadResult z licznikami."""
    from pbn_integrator.utils.mongodb_ops import pobierz_mongodb

    elems = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    fun = _fun_failing_on("b")
    result = pobierz_mongodb(
        elems, MagicMock(), fun=fun, disable_progress_bar=True, on_error="skip"
    )
    # „a” i „c” zapisane mimo błędu na „b”.
    assert fun.saved == ["a", "c"]
    assert result.processed == 2
    assert result.errored == 1


def test_on_error_nieznana_wartosc_to_valueerror():
    """Literówka w ``on_error`` fail-uje głośno, nie po cichu wybiera tryb."""
    from pbn_integrator.utils.mongodb_ops import pobierz_mongodb

    with pytest.raises(ValueError, match="on_error"):
        pobierz_mongodb([], MagicMock(), fun=lambda *a, **k: None, on_error="whatever")
