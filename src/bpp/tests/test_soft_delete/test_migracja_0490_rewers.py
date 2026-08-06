"""Odwracalność migracji 0490 (warunkowy UniqueConstraint/ExclusionConstraint
na *_Autor + zastąpienie legacy `RunSQL` constraintu z migracji 0132).

``backward`` musi przywrócić DOKŁADNIE stan sprzed migracji: bezwarunkowy
`unique_together` ORAZ legacy `UNIQUE (rekord_id, kolejnosc) DEFERRABLE
INITIALLY DEFERRED` — inaczej rollback zostawia bazę bez żadnego z dwóch
mechanizmów pilnujących unikalności kolejności autorów.
"""

import pytest
from django.core.management import call_command
from django.db import connection

TABELE = [
    "bpp_patent_autor",
    "bpp_wydawnictwo_ciagle_autor",
    "bpp_wydawnictwo_zwarte_autor",
]

LEGACY_CONSTRAINT = {
    "bpp_patent_autor": "bpp_patent_autor_unique_rekord_id_kolejnosc",
    "bpp_wydawnictwo_ciagle_autor": (
        "bpp_wydawnictwo_ciagle_autor_unique_rekord_id_kolejnosc"
    ),
    "bpp_wydawnictwo_zwarte_autor": (
        "bpp_wydawnictwo_zwarte_autor_unique_rekord_id_kolejnosc"
    ),
}

PREFIX = {
    "bpp_patent_autor": "pat",
    "bpp_wydawnictwo_ciagle_autor": "wc",
    "bpp_wydawnictwo_zwarte_autor": "wz",
}


def _constraint_names(cur, tabela):
    """Nazwy ograniczeń (`pg_constraint`) i indeksów (`pg_indexes`) na
    tabeli. Warunkowy `UniqueConstraint` (`condition=...`) w Postgresie NIE
    jest zapisany w `pg_constraint` — Postgres nie ma składni `ADD
    CONSTRAINT ... UNIQUE ... WHERE`, więc Django realizuje go jako zwykły
    `CREATE UNIQUE INDEX ... WHERE ...` (widoczny tylko w `pg_indexes`).
    `ExclusionConstraint` i zwykłe `UNIQUE` SĄ pełnoprawnymi constraintami
    (`pg_constraint`, `contype='x'`/`'u'`). Stąd suma obu źródeł."""
    cur.execute(
        "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass",
        [tabela],
    )
    nazwy = {row[0] for row in cur.fetchall()}
    cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s", [tabela])
    nazwy |= {row[0] for row in cur.fetchall()}
    return nazwy


@pytest.mark.django_db
def test_migracja_0490_odwracalna():
    with connection.cursor() as cur:
        for tabela in TABELE:
            nazwy = _constraint_names(cur, tabela)
            prefix = PREFIX[tabela]
            assert f"{prefix}_autor_uniq_rekord_autor_typ" in nazwy
            assert f"{prefix}_autor_uniq_rekord_autor_kolejnosc" in nazwy
            assert f"{prefix}_autor_excl_rekord_kolejnosc" in nazwy
            assert LEGACY_CONSTRAINT[tabela] not in nazwy

    call_command("migrate", "bpp", "0489", verbosity=0)

    with connection.cursor() as cur:
        for tabela in TABELE:
            nazwy = _constraint_names(cur, tabela)
            prefix = PREFIX[tabela]
            assert f"{prefix}_autor_uniq_rekord_autor_typ" not in nazwy
            assert f"{prefix}_autor_uniq_rekord_autor_kolejnosc" not in nazwy
            assert f"{prefix}_autor_excl_rekord_kolejnosc" not in nazwy
            assert LEGACY_CONSTRAINT[tabela] in nazwy

    call_command("migrate", "bpp", "0490", verbosity=0)

    with connection.cursor() as cur:
        for tabela in TABELE:
            nazwy = _constraint_names(cur, tabela)
            prefix = PREFIX[tabela]
            assert f"{prefix}_autor_uniq_rekord_autor_typ" in nazwy
            assert f"{prefix}_autor_uniq_rekord_autor_kolejnosc" in nazwy
            assert f"{prefix}_autor_excl_rekord_kolejnosc" in nazwy
            assert LEGACY_CONSTRAINT[tabela] not in nazwy
