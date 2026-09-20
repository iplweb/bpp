"""Task 3c, runda poprawek 1 (Important 1): warunkowe UniqueConstraint/
ExclusionConstraint na *_Autor są CZĘŚCIOWE (``WHERE deleted_at IS NULL``) —
nie pokrywają już zapytań po samym ``rekord`` bez tego predykatu (RI-check
Postgresa przy DELETE rodzica, kolektor kaskady Django, `global_objects`/
`deleted_objects`.filter(rekord=…)). FK musi więc mieć z powrotem zwykły,
BEZWARUNKOWY indeks z ``rekord_id`` jako kolumną wiodącą."""

import pytest
from django.db import connection

TABELE = [
    "bpp_patent_autor",
    "bpp_wydawnictwo_ciagle_autor",
    "bpp_wydawnictwo_zwarte_autor",
]


def _ma_bezwarunkowy_indeks_na_rekord_id(cur, tabela):
    """Czy tabela ma indeks btree z `rekord_id` jako PIERWSZĄ kolumną i BEZ
    klauzuli WHERE (częściowe indeksy z Taska 3c się nie liczą — nie
    przyspieszają zapytań bez predykatu `deleted_at IS NULL`)."""
    cur.execute(
        "SELECT indexdef FROM pg_indexes WHERE tablename = %s",
        [tabela],
    )
    for (indexdef,) in cur.fetchall():
        if "WHERE" in indexdef:
            continue
        # np. "... USING btree (rekord_id)" albo "(rekord_id, ...)"
        if "(rekord_id)" in indexdef or "(rekord_id," in indexdef:
            return True
    return False


@pytest.mark.django_db
@pytest.mark.parametrize("tabela", TABELE)
def test_rekord_ma_bezwarunkowy_indeks(tabela):
    with connection.cursor() as cur:
        assert _ma_bezwarunkowy_indeks_na_rekord_id(cur, tabela), (
            f"{tabela}: brak bezwarunkowego indeksu na rekord_id — "
            "RI-check/kaskada/global_objects.filter(rekord=…) robiłyby "
            "seq scan"
        )
