"""Rodzina ``bpp_kronika_*`` została skasowana (migracja ``0499``).

Siedem martwych widoków, kasowanych jednym cięciem, bo graf zależności
(``bpp_kronika_view`` <- ``bpp_kronika_all_unsorted_view`` <- pięć liści)
nie daje się rozciąć na raty bez ``CASCADE``.
"""

import pytest
from django.core.management import call_command
from django.db import connection

RODZINA = [
    "bpp_kronika_view",
    "bpp_kronika_all_unsorted_view",
    "bpp_kronika_wydawnictwo_ciagle_view",
    "bpp_kronika_wydawnictwo_zwarte_view",
    "bpp_kronika_patent_view",
    "bpp_kronika_praca_doktorska_view",
    "bpp_kronika_praca_habilitacyjna_view",
]


def _istniejace(cur):
    cur.execute(
        "SELECT viewname FROM pg_views "
        "WHERE schemaname = 'public' AND viewname = ANY(%s)",
        [RODZINA],
    )
    return {r[0] for r in cur.fetchall()}


@pytest.mark.django_db
def test_rodzina_kronika_nie_istnieje():
    with connection.cursor() as cur:
        zostale = _istniejace(cur)
    assert not zostale, f"widoki kronika nadal istnieja: {sorted(zostale)}"


@pytest.mark.django_db
def test_0499_odwracalna():
    """``backward`` odtwarza całą siódemkę z sidecara ``.sql``.

    Sidecar był generowany maszynowo z ``pg_get_viewdef()``, ale to nie
    dowodzi, że da się go ODTWORZYĆ — kolejność ``CREATE VIEW`` musi
    respektować graf zależności, a ``pg_get_viewdef`` nie zwraca jej sam
    z siebie. Ten test jest jedynym sprawdzeniem tej kolejności.
    """
    try:
        call_command("migrate", "bpp", "0498", verbosity=0)

        with connection.cursor() as cur:
            odtworzone = _istniejace(cur)
        brakujace = set(RODZINA) - odtworzone
        assert not brakujace, (
            f"backward nie odtworzyl: {sorted(brakujace)} — sprawdz kolejnosc "
            f"CREATE VIEW w sidecarze 0499_drop_kronika_views.sql"
        )
    finally:
        # ZAWSZE wracamy na szczyt: baza testowa jest wspoldzielona przez
        # caly przebieg, wiec zostawienie jej z odtworzona kronika psuloby
        # test_rodzina_kronika_nie_istnieje w kolejnych plikach.
        call_command("migrate", "bpp", verbosity=0)

    with connection.cursor() as cur:
        assert not _istniejace(cur), "po ponownym forward kronika nie znikla"
