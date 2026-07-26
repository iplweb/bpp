"""Tabele krzyżowe (pivot) — generyczny silnik + rejestry per model."""

from .core import (  # noqa: F401
    BRAK,
    PIVOT_MAX_CELLS,
    PIVOT_MAX_PAIRS,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    zbuduj_pivot,
)


def wybierz_rejestr_pivota(model_key):
    """Rejestr pivota dla modelu przeszukiwanego na stronie zapytania.

    Oba rejestry (`bpp.pivot.rekord`, `bpp.pivot.autor`) wystawiają ten sam
    interfejs: `DIMENSIONS`, `METRICS`, `parse_params(GET)`,
    `zbuduj(base_qs, row, col, metric)` — widok (`ZapytanieView._pivot_context`)
    i eksport (`ZapytanieExportView._eksport_pivota`) wołają ten helper
    zamiast trzymać dwie kopie tego samego `if`-a.
    """
    if model_key == "autor":
        from . import autor

        return autor
    from . import rekord

    return rekord
