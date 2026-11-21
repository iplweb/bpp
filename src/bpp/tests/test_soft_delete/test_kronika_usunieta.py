"""Rodzina ``bpp_kronika_*`` została skasowana (migracja ``0514``).

Siedem martwych widoków, kasowanych jednym cięciem, bo graf zależności
(``bpp_kronika_view`` <- ``bpp_kronika_all_unsorted_view`` <- pięć liści)
nie daje się rozciąć na raty bez ``CASCADE``.
"""

import pytest
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
