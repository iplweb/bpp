"""Odwracalność serii 0490-0493 (Task 3c): warunkowe ograniczenia na *_Autor.

Task 3c był pierwotnie jedną migracją (0490); jest rozbity na cztery
(indeks FK / unique po typie / exclusion po kolejności / zdjęcie starych),
każda z ``atomic = False`` — patrz docstring ``0490_autor_indeks_fk_rekord``.

``backward`` całej serii musi przywrócić DOKŁADNIE stan sprzed niej:
bezwarunkowy ``unique_together`` ORAZ legacy ``UNIQUE (rekord_id, kolejnosc)
DEFERRABLE INITIALLY DEFERRED`` — inaczej rollback zostawia bazę bez żadnego
z dwóch mechanizmów pilnujących unikalności kolejności autorów.

Test zjeżdża do 0489 i wraca do NAJNOWSZEJ migracji ``bpp`` (``migrate bpp``
bez numeru). Powrót „do 0490" byłby błędem: baza testowa jest współdzielona
przez cały przebieg (``--reuse-db``), więc pozostawienie migracji późniejszych
niż cel jako niezastosowanych psułoby kolejne testy.
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


def _sprawdz_stan_po(cur):
    for tabela in TABELE:
        nazwy = _constraint_names(cur, tabela)
        prefix = PREFIX[tabela]
        assert f"{prefix}_autor_uniq_rekord_autor_typ" in nazwy
        assert f"{prefix}_autor_excl_rekord_kolejnosc" in nazwy
        # Redundantny wobec `..._excl_rekord_kolejnosc` (ten nie patrzy na
        # autora, więc jest ściśle silniejszy) — świadomie NIE tworzony.
        assert f"{prefix}_autor_uniq_rekord_autor_kolejnosc" not in nazwy
        assert LEGACY_CONSTRAINT[tabela] not in nazwy


@pytest.mark.django_db
def test_migracje_0490_0493_odwracalne(bez_reinstalacji_denorma):
    with connection.cursor() as cur:
        _sprawdz_stan_po(cur)

    call_command("migrate", "bpp", "0489", verbosity=0)

    with connection.cursor() as cur:
        for tabela in TABELE:
            nazwy = _constraint_names(cur, tabela)
            prefix = PREFIX[tabela]
            assert f"{prefix}_autor_uniq_rekord_autor_typ" not in nazwy
            assert f"{prefix}_autor_excl_rekord_kolejnosc" not in nazwy
            assert LEGACY_CONSTRAINT[tabela] in nazwy

    call_command("migrate", "bpp", verbosity=0)

    with connection.cursor() as cur:
        _sprawdz_stan_po(cur)
