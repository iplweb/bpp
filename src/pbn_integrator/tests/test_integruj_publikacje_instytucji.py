"""Regression tests for ``integruj_publikacje_instytucji`` dispatch.

Geneza: komenda ``pbn_integrator`` (etap 17) wołała::

    integruj_publikacje_instytucji(dm, skip_pages=skip_pages, ...)

gdzie ``dm`` (bool z ``--disable-multiprocessing``) trafiał POZYCYJNIE w
parametr ``skip_pages``, a ``skip_pages=skip_pages`` przekazywało go PONOWNIE →
``TypeError: ... got multiple values for argument 'skip_pages'``. Etap był
martwy odkąd zrefaktoryzowano sygnaturę. Te testy pilnują, że funkcję da się
zawołać tak, jak robi to komenda, oraz że intencja flagi/wątków dociera do
właściwego helpera dyspozytorskiego.
"""

import pytest

from pbn_integrator.utils import integration


@pytest.mark.django_db
def test_integruj_publikacje_instytucji_command_call_shape(monkeypatch):
    """Wywołanie w kształcie z komendy nie rzuca TypeError i idzie w MP-path.

    Komenda woła z ``disable_multiprocessing=`` (po naprawie). Sprawdzamy, że
    przy braku ``use_threads`` trafiamy w ``_integruj_publikacje`` (nie w wersję
    wątkową) i że ``skip_pages`` jest poprawnie przekazane.
    """
    captured = {}

    def fake_integruj_publikacje(pubs, **kwargs):
        captured["path"] = "multiprocessing"
        captured["kwargs"] = kwargs

    def fake_threaded(pubs, **kwargs):
        captured["path"] = "threaded"
        captured["kwargs"] = kwargs

    monkeypatch.setattr(integration, "_integruj_publikacje", fake_integruj_publikacje)
    monkeypatch.setattr(integration, "_integruj_publikacje_threaded", fake_threaded)

    # Dokładnie taki kształt wywołania, jaki ma komenda (etap 17).
    integration.integruj_publikacje_instytucji(
        disable_multiprocessing=True,
        skip_pages=3,
        uczelnia=None,
    )

    assert captured["path"] == "multiprocessing"
    assert captured["kwargs"]["skip_pages"] == 3
    # Historyczny, bezpieczny default: MP-path zawsze single-process.
    assert captured["kwargs"]["disable_multiprocessing"] is True


@pytest.mark.django_db
def test_integruj_publikacje_instytucji_threaded_path(monkeypatch):
    """``use_threads=True`` rutuje do wersji wątkowej, propaguje disable->thread."""
    captured = {}

    monkeypatch.setattr(
        integration,
        "_integruj_publikacje",
        lambda pubs, **kw: captured.update(path="multiprocessing", kwargs=kw),
    )
    monkeypatch.setattr(
        integration,
        "_integruj_publikacje_threaded",
        lambda pubs, **kw: captured.update(path="threaded", kwargs=kw),
    )

    integration.integruj_publikacje_instytucji(
        use_threads=True,
        disable_multiprocessing=True,
        skip_pages=0,
    )

    assert captured["path"] == "threaded"
    assert captured["kwargs"]["disable_threading"] is True
