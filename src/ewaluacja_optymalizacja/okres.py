"""Okres ewaluacji w module optymalizacji.

Widoki biorą okres z ``ewaluacja_common.okres.okres_dla_request(request)``,
a zadania Celery dostają go jawnie (``okres_pk``) — nigdy nie czytają sesji.
Ten moduł zbiera drobne helpery wspólne dla widoków, zadań i solvera.
"""

from ewaluacja_common import okres as okres_common

#: Limit slotów autora na jeden rok okresu (4 sloty za 4 lata 2022–2025).
SLOTY_AUTORA_NA_ROK = 1.0

#: Limit slotów monografii autora na jeden rok okresu (2 sloty za 4 lata).
SLOTY_MONOGRAFII_NA_ROK = 0.5


def domyslny_okres_pk():
    """Wartość domyślna pól ``okres`` modeli wyników: okres zawierający
    bieżący rok. ``None``, gdy tabela okresów jest pusta."""
    okres = okres_common.okres_domyslny()
    return okres.pk if okres is not None else None


def pobierz_okres(okres=None):
    """Zwróć obiekt ``OkresEwaluacji`` z obiektu, klucza głównego albo
    ``None`` (wtedy okres domyślny)."""
    from ewaluacja_common.models import OkresEwaluacji

    if okres is None:
        okres = okres_common.okres_domyslny()
        if okres is None:
            raise OkresEwaluacji.DoesNotExist("Brak zdefiniowanych okresów ewaluacji")
        return okres
    if isinstance(okres, OkresEwaluacji):
        return okres
    return OkresEwaluacji.objects.get(pk=okres)


def okres_z_roku(rok=None):
    """Okres dla opcji ``--okres ROK`` komend CLI: okres zawierający ``rok``
    (``None`` = okres domyślny wg bieżącego roku)."""
    if rok is None:
        return pobierz_okres(None)
    okres = okres_common.okres_domyslny(rok)
    if okres is None:
        return pobierz_okres(None)
    return okres


def limity_slotow_autora(okres):
    """Regulaminowe maksimum slotów autora za cały okres: ``(ogółem,
    monografie)``. Dla 4 lat (2022–2025) to (4.0, 2.0); skaluje się liniowo
    z liczbą lat okresu."""
    lat = okres.liczba_lat
    return SLOTY_AUTORA_NA_ROK * lat, SLOTY_MONOGRAFII_NA_ROK * lat


def filtr_lat(okres, prefix=""):
    """Słownik lookupów Django ograniczających ``<prefix>rok`` do lat okresu,
    np. ``filtr_lat(okres, "rekord__")`` → ``{"rekord__rok__gte": ...}``."""
    return {
        f"{prefix}rok__gte": okres.rok_od,
        f"{prefix}rok__lte": okres.rok_do,
    }
