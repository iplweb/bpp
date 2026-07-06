"""Zawężanie querysetów MetrykaAutora do uczelni oglądającego (read-side).

Hybryda uczelni (site + superuser ?uczelnia=) rozstrzygana w widoku przez
`raport_slotow.uczelnia_helper.uczelnia_dla_odczytu`; tutaj sam filtr +
guard single-install (no-op przy dokładnie jednej uczelni, jak R1/R3a).
"""

from bpp.util.uczelnia_scope import tylko_jedna_uczelnia


def scope_metryki(qs, uczelnia):
    """Zawęź queryset MetrykaAutora do uczelni; no-op przy single-install/None."""
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(uczelnia=uczelnia)
