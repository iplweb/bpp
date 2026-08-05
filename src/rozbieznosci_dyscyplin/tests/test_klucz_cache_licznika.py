"""Testy DETERMINIZMU klucza cache licznika `CachingPaginator`.

Ten sam defekt co przy advisory lockach (`django_bpp.db_locks`): klucz
liczony wbudowanym `hash()` jest solony PYTHONHASHSEED-em, więc różni się
między procesami. Tu nie psuje poprawności, tylko skuteczność cache —
każdy worker gunicorna miał własną przestrzeń kluczy i nie czytał wpisów
pozostałych.

Determinizmu nie da się sprawdzić w jednym procesie (tam `hash()` też jest
stabilny), dlatego klucz liczymy w OSOBNYCH procesach z różnymi ziarnami.
"""

import os
import subprocess
import sys
import textwrap

from rozbieznosci_dyscyplin.admin_utils import klucz_cache_licznika

ZIARNA = ["0", "1", "42", "1000", "123456"]

SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SQL = 'SELECT "bpp_autor"."id" FROM "bpp_autor" WHERE "bpp_autor"."rok" = 2024'


def _w_osobnym_procesie(kod: str, ziarno: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=ziarno, PYTHONPATH=SRC)
    wynik = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(kod)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=True,
    )
    return wynik.stdout.strip()


def test_klucz_jest_identyczny_miedzy_procesami():
    """Ten sam klucz w pięciu procesach o różnych PYTHONHASHSEED.

    Bez tego cache licznika w praktyce nie działa w wielo-procesowej
    produkcji (N workerów = N rozłącznych przestrzeni kluczy).
    """
    kod = f"""
        import hashlib
        skrot = hashlib.blake2s({SQL!r}.encode("utf-8"), digest_size=8).hexdigest()
        print(f"adm:{{skrot}}:count")
    """
    wyniki = {_w_osobnym_procesie(kod, z) for z in ZIARNA}

    assert len(wyniki) == 1, (
        f"klucz cache RÓŻNI SIĘ między procesami: {sorted(wyniki)} — "
        "workery nie współdzielą wpisów"
    )
    assert wyniki == {klucz_cache_licznika(SQL)}


def test_wbudowany_hash_rozjezdza_sie_miedzy_procesami():
    """Kontrola metody: stara implementacja MUSI dać różne klucze.

    Inaczej test wyżej przechodziłby również na zepsutym kodzie.
    """
    kod = f'print(f"adm:{{hash({SQL!r})}}:count")'
    wyniki = {_w_osobnym_procesie(kod, z) for z in ZIARNA}

    assert len(wyniki) > 1, (
        "PYTHONHASHSEED nie wpłynął na hash() — metodyka testu determinizmu "
        "jest nieważna"
    )


def test_to_samo_zapytanie_ten_sam_klucz():
    assert klucz_cache_licznika(SQL) == klucz_cache_licznika(SQL)


def test_rozne_zapytania_rozne_klucze():
    inny = SQL.replace("2024", "2025")
    assert klucz_cache_licznika(SQL) != klucz_cache_licznika(inny)


def test_ksztalt_klucza():
    """Prefiks `adm:` zachowany, klucz krótki (Redis go trzyma)."""
    klucz = klucz_cache_licznika(SQL)

    assert klucz.startswith("adm:")
    assert klucz.endswith(":count")
    assert len(klucz) == len("adm:") + 16 + len(":count")
