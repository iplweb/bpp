"""Cienka fasada nad tqdm — pozwala wylaczyc w testach.

Opcjonalny obserwator postępu (``obserwuj_postep``) dostaje każdy krok
każdego paska — tak kreator pierwszego uruchomienia pokazuje w przeglądarce
postęp generowania danych demo, choć generatory znają tylko ``make_progress``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

from tqdm import tqdm

T = TypeVar("T")

# callback(desc, n, total) — ``n`` elementów paska ``desc`` za nami
# (0 = pasek właśnie wystartował); ``total`` bywa None (nieznana długość).
ObserwatorPostepu = Callable[[str, int, "int | None"], None]

_obserwator: ContextVar[ObserwatorPostepu | None] = ContextVar(
    "demo_data_obserwator_postepu", default=None
)


@contextmanager
def obserwuj_postep(callback: ObserwatorPostepu):
    """Przez czas bloku każdy pasek ``make_progress`` raportuje do ``callback``."""
    token = _obserwator.set(callback)
    try:
        yield
    finally:
        _obserwator.reset(token)


def make_progress(
    iterable: Iterable[T],
    *,
    desc: str,
    total: int | None = None,
    disable: bool = False,
) -> Iterator[T]:
    """Zwraca tqdm-iterator lub goly iterator gdy disable=True."""
    pasek = tqdm(iterable, desc=desc, total=total, disable=disable)
    callback = _obserwator.get()
    if callback is None:
        return pasek
    return _z_obserwatorem(pasek, desc, getattr(pasek, "total", total), callback)


def _z_obserwatorem(
    pasek: Iterable[T], desc: str, total: int | None, callback: ObserwatorPostepu
) -> Iterator[T]:
    callback(desc, 0, total)
    for n, element in enumerate(pasek, start=1):
        yield element
        callback(desc, n, total)
