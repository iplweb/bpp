"""Zawężanie querysetów MetrykaAutora do uczelni oglądającego (read-side)
i do wybranego okresu ewaluacji.

Hybryda uczelni (site + superuser ?uczelnia=) rozstrzygana w widoku przez
`raport_slotow.uczelnia_helper.uczelnia_dla_odczytu`; tutaj sam filtr +
guard single-install (no-op przy dokładnie jednej uczelni, jak R1/R3a).
Okres w widokach: `ewaluacja_common.okres.okres_dla_request`.
"""

from bpp.util.uczelnia_scope import tylko_jedna_uczelnia


def scope_metryki(qs, uczelnia, okres=None):
    """Zawęź queryset MetrykaAutora do uczelni (no-op przy single-install/None)
    oraz — gdy podano — do okresu ewaluacji."""
    if okres is not None:
        qs = qs.filter(okres=okres)
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(uczelnia=uczelnia)
