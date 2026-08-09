"""Odwracalność migracji 0489 (widoki + gałąź kasująca + bramka WHEN).

``backward`` musi zdjąć WSZYSTKIE trzy zmiany — inaczej rollback zostawia
niespójny stan: np. widok bez filtra, ale funkcja z gałęzią kasującą (kasowałaby
wiersze, których widok i tak nie odfiltrował) albo bramka znająca ``deleted_at``
przy funkcji, która nic z tym nie robi.

Test siedzi w zwykłej transakcji testowej (``django_db`` bez
``transaction=True``): DDL w Postgresie jest transakcyjny, więc obie zmiany
(unapply + reapply) i wpisy w ``django_migrations`` cofną się razem z nią.
"""

import pytest
from django.core.management import call_command
from django.db import connection

WIDOKI = [
    "bpp_wydawnictwo_ciagle_autorzy",
    "bpp_wydawnictwo_zwarte_autorzy",
    "bpp_patent_autorzy",
]
FUNKCJE = [
    "bpp_refresh_autor_wydawnictwo_ciagle",
    "bpp_refresh_autor_wydawnictwo_zwarte",
    "bpp_refresh_autor_patent",
]
TRIGGERY = [
    ("bpp_wydawnictwo_ciagle_autor", "bpp_wydawnictwo_ciagle_autor_cache_upd"),
    ("bpp_wydawnictwo_zwarte_autor", "bpp_wydawnictwo_zwarte_autor_cache_upd"),
    ("bpp_patent_autor", "bpp_patent_autor_cache_upd"),
]


def _viewdef(cur, widok):
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
    return cur.fetchone()[0]


def _funcdef(cur, fn):
    cur.execute("SELECT pg_get_functiondef(%s::regproc)", [fn])
    return cur.fetchone()[0]


def _triggerdef(cur, tabela, trigger):
    cur.execute(
        "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
        "WHERE t.tgrelid = %s::regclass AND t.tgname = %s",
        [tabela, trigger],
    )
    return cur.fetchone()[0]


def _stan_ddl(cur):
    return (
        [_viewdef(cur, w) for w in WIDOKI],
        [_funcdef(cur, f) for f in FUNKCJE],
        [_triggerdef(cur, t, g) for t, g in TRIGGERY],
    )


@pytest.mark.django_db
# Ten test odtwarza migracje w OBIE strony (unapply do 0488, reapply do
# HEAD-a), więc jego czas rośnie z każdą kolejną migracją w gałęzi — faza 04
# dołożyła `0501` i `0502`. Solo mieści się w ~45 s, ale w pełnym przebiegu
# na ~10 workerach xdist rywalizuje o CPU i bazę i przekraczał globalne
# `--timeout 90` z `pytest.ini`. Padał wtedy w TEARDOWNIE, przy zielonym
# teście — objaw mylący, bo wyglądał na błąd migracji.
@pytest.mark.timeout(300)
def test_migracja_0489_odwracalna(bez_reinstalacji_denorma):
    with connection.cursor() as cur:
        przed = _stan_ddl(cur)

    call_command("migrate", "bpp", "0488_autor_soft_delete_fields", verbosity=0)

    with connection.cursor() as cur:
        for widok in WIDOKI:
            assert "deleted_at" not in _viewdef(cur, widok), (
                f"{widok}: backward nie zdjął filtra"
            )
        for fn in FUNKCJE:
            assert "NEW.deleted_at" not in _funcdef(cur, fn), (
                f"{fn}: backward nie zdjął gałęzi kasującej"
            )
        for tabela, trigger in TRIGGERY:
            assert "deleted_at" not in _triggerdef(cur, tabela, trigger), (
                f"{trigger}: backward nie przeliczył bramki WHEN"
            )
        # Widoki muszą zachować listę i typy kolumn — inaczej UNION bpp_autorzy
        # (zależny od całej trójki) rozsypałby się przy pierwszym odczycie.
        cur.execute("SELECT count(*) FROM bpp_autorzy")
        cur.fetchone()

    call_command("migrate", "bpp", verbosity=0)

    with connection.cursor() as cur:
        assert _stan_ddl(cur) == przed, (
            "forward po backward nie odtworzył identycznego DDL"
        )
