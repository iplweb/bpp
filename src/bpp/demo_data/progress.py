"""Cienka fasada nad tqdm — pozwala wylaczyc w testach."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TypeVar

from tqdm import tqdm

T = TypeVar("T")


def make_progress(
    iterable: Iterable[T],
    *,
    desc: str,
    total: int | None = None,
    disable: bool = False,
) -> Iterator[T]:
    """Zwraca tqdm-iterator lub goly iterator gdy disable=True."""
    return tqdm(iterable, desc=desc, total=total, disable=disable)
