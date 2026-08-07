"""Odwracalność ``0497``: filtr soft-delete w widokach publikacji.

``0497.backward`` nie odtwarza definicji widoków z plików ``.sql`` (jak robi
to ``0489.backward`` dla ścieżki autorstwa), bo widoki publikacji były
redefiniowane w kilku migracjach — m.in. ``0494`` dokładająca
``count(...) FILTER`` — i nie ma jednego pliku źródłowego. Zamiast tego
usuwa DOKŁADNIE ten tekst, który wstawiła ``_z_filtrem``.

To rozwiązanie symetryczne, ale i kruche: literówka w usuwanym fragmencie
albo zmiana kształtu definicji sprawia, że ``_bez_filtra`` albo rzuci
wyjątkiem, albo (gorzej) zostawi widok z filtrem. Ten test jest jedynym
dowodem, że cykl forward->backward->forward faktycznie domyka się na żywym
katalogu.

Test zjeżdża do ``0496`` i wraca do NAJNOWSZEJ migracji ``bpp``
(``migrate bpp`` bez numeru) — powrót „do 0497" byłby błędem, bo baza
testowa jest współdzielona przez cały przebieg i migracje późniejsze niż cel
zostałyby niezastosowane, psując kolejne testy.
"""

import pytest
from django.core.management import call_command
from django.db import connection

from bpp.tests.test_soft_delete.test_kanarek_katalogowy import (
    _widoki_zalezne_od_deleted_at,
)

TABELE = [
    "bpp_wydawnictwo_ciagle",
    "bpp_wydawnictwo_zwarte",
    "bpp_patent",
    "bpp_praca_doktorska",
    "bpp_praca_habilitacyjna",
]

# 7 widokow: 5 rekordowych + 2 autorskie (doktorat/habilitacja maja autora
# na wlasnym wierszu, wiec ich widoki *_autorzy tez czytaja tabele publikacji)
OCZEKIWANE_PARY = {(t + "_view", t) for t in TABELE} | {
    (t + "_autorzy", t) for t in ("bpp_praca_doktorska", "bpp_praca_habilitacyjna")
}


def _pary_zalezne():
    with connection.cursor() as cur:
        return _widoki_zalezne_od_deleted_at(cur, TABELE)


@pytest.mark.django_db
def test_0497_odwracalna(bez_reinstalacji_denorma):
    # Stan wyjsciowy: wszystkie 7 widokow zalezy od deleted_at swojej tabeli.
    assert OCZEKIWANE_PARY <= _pary_zalezne(), (
        "stan przed testem juz jest niepoprawny — migracja 0497 nie jest "
        "zastosowana albo widoki zostaly zmienione"
    )

    try:
        call_command("migrate", "bpp", "0496", verbosity=0)

        po_cofnieciu = _pary_zalezne()
        nadmiarowe = OCZEKIWANE_PARY & po_cofnieciu
        assert not nadmiarowe, (
            f"backward NIE zdjal filtra z: {sorted(nadmiarowe)} — "
            "_bez_filtra nie usunelo wstawki"
        )
    finally:
        # ZAWSZE wracamy do najnowszej, nawet gdy asercja wyzej padnie —
        # inaczej zostawiamy wspoldzielona baze testowa w stanie sprzed 0497
        # i psujemy kazdy kolejny test w przebiegu.
        call_command("migrate", "bpp", verbosity=0)

    assert OCZEKIWANE_PARY <= _pary_zalezne(), (
        "po ponownym forward filtr nie wrocil do wszystkich 7 widokow"
    )
