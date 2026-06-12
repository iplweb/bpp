"""Zawężanie querysetów Rekordów do uczelni oglądającego (multi-hosted, read-side).

Jedno źródło reguły rekordowej + guard single-install. Reguła atrybucji =
strona główna (``get_uczelnia_context_data``): rekord należy do uczelni, gdy
którakolwiek z jednostek zapisanych na autorstwie należy do tej uczelni.
BEZ ``skupia_pracownikow`` (włącznie z obcą jednostką) — świadoma decyzja
(spec R3a).
"""


def tylko_jedna_uczelnia() -> bool:
    """True, gdy w systemie jest dokładnie jedna uczelnia.

    Fast-track jak ``IPunktacjaCacher._uczelnie_do_przeliczenia``: przy jednej
    uczelni filtr per-uczelnia jest no-op, więc pomijamy go (i kosztowny JOIN).
    """
    from bpp.models import Uczelnia

    return Uczelnia.objects.count() == 1


def scope_rekord_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Rekord`` do uczelni oglądającego.

    No-op (zwraca ten sam qs) gdy brak uczelni (brak mapowania Site→Uczelnia)
    albo gdy w systemie jest dokładnie jedna uczelnia — wynik identyczny,
    a unikamy JOIN-a przez M2M ``autorzy`` + ``DISTINCT``.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(autorzy__jednostka__uczelnia=uczelnia).distinct()
