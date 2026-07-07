"""Guard multi-hosted: pilnuje, że footguny „pierwszej-z-brzegu uczelni"
nie wracają do kodu runtime.

NIE MA „uczelni domyślnej". ``Uczelnia.objects.get_default()`` /
``Uczelnia.objects.default`` zostały TRWALE USUNIĘTE — każde ich wystąpienie
w ``src/`` (poza testami/migracjami) to regresja. Uczelnię ustala się z
requestu (``get_for_request`` → domena → Site → Uczelnia); gdy się NIE DA,
jedyny dozwolony fallback to ``get_single_uczelnia_or_none`` (jedna albo None,
bez zgadywania) lub ``get_single_uczelnia_or_fail`` (jedna albo głośny błąd).

Drugi, semantycznie równoważny footgun to ``Uczelnia.objects.first()`` /
``Uczelnia.objects.all()[0]`` — pilnowany osobno (whitelista demo/debug/
warstwa-modelu/UI default).

Gdy ten test PADA:
- dla get_default → USUNĄŁEŚ regres: ``Uczelnia.objects.get_default()``/
  ``.default`` NIE WOLNO użyć (metoda nie istnieje). Użyj jawnej uczelni
  (``get_for_request`` / argument / FK obiektu) albo ``get_single_uczelnia_*``.
- dla first() → użyj jawnej uczelni / single-or-fail, albo dopisz do
  ``APPROVED_FIRST`` z uzasadnieniem (gdy to świadomy fallback bez requestu).

Patrz: docs/deweloper/audyt-multihosted-pbn.md
"""

import re
from pathlib import Path

# TWARDY ZAKAZ: ``Uczelnia.objects.get_default()`` / ``Uczelnia.objects.default``
# nie istnieją już jako API — 0 dozwolonych wystąpień (też w komentarzach, żeby
# nie sugerować nieistniejącej metody).
PATTERN = re.compile(r"Uczelnia\.objects\.(?:get_default\(\)|default\b)")

# Drugi footgun, semantycznie równoważny: ``Uczelnia.objects.first()`` /
# ``Uczelnia.objects.all()[0]`` zgaduje „pierwszą-z-brzegu" uczelnię niezależnie
# od hosta z requestu. ``all()[0]`` dorzucony prewencyjnie (0 wystąpień dziś).
PATTERN_FIRST = re.compile(r"Uczelnia\.objects\.(?:first\(\)|all\(\)\s*\[\s*0\s*\])")

SRC = Path(__file__).resolve().parents[2]  # .../src

# Whitelist dla ``Uczelnia.objects.first()``. Każdy wpis to ŚWIADOMY fallback
# bez requestu (warstwa modelu / UI default / demo / debug / komentarz).
APPROVED_FIRST: dict[str, int] = {
    "bpp/demo_data/generators/uczelnia.py": 1,  # demo/seed, CLI bez requestu
    "bpp/management/commands/debug_setup_initial_data.py": 1,  # debug command, None-tolerant
    "bpp/models/jednostka.py": 1,  # KOMENTARZ (nie kod) — zakomentowany default=lambda
}


def _scan(pattern: re.Pattern) -> dict[str, int]:
    found: dict[str, int] = {}
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if "/tests/" in f"/{rel}" or "/migrations/" in f"/{rel}":
            continue
        if path.name.startswith("test_") or path.name == "tests.py":
            continue
        n = len(pattern.findall(path.read_text(encoding="utf-8")))
        if n:
            found[rel] = n
    return found


def test_get_default_usuniete_na_trwale():
    """``Uczelnia.objects.get_default()`` / ``.default`` NIE MOŻE istnieć w
    runtime — metoda i cached_property zostały usunięte (nie ma „uczelni
    domyślnej"). Każde wystąpienie = regresja do footguna pierwszej-z-brzegu.
    """
    found = _scan(PATTERN)

    assert not found, (
        "Znaleziono Uczelnia.objects.get_default()/.default — ten byt został "
        f"USUNIĘTY na trwałe (nie ma uczelni domyślnej): {found}. Użyj jawnej "
        "uczelni (get_for_request / argument / FK obiektu) albo "
        "get_single_uczelnia_or_none / get_single_uczelnia_or_fail."
    )


def test_first_poza_whitelista_to_regresja_multihosted():
    """``Uczelnia.objects.first()`` w runtime to ten sam bug co get_default:
    wybiera pierwszą-z-brzegu uczelnię zamiast tej z requestu/argumentu.

    Gdy ten test PADA:
    - DODAŁEŚ ``Uczelnia.objects.first()`` → użyj JAWNEJ uczelni:
      ``uczelnia_dla_odczytu(request)`` / ``get_for_request(request)`` w
      widokach, argument przekazany od wołającego, albo single-or-fail
      (``get()`` z CommandError) w komendach CLI. Jeśli miejsce jest NAPRAWDĘ
      akceptowalne (warstwa modelu / UI default / demo / debug) — dopisz je do
      ``APPROVED_FIRST`` z uzasadnieniem.
    - USUNĄŁEŚ ``first()`` (naprawiłeś multi-hosted) → zmniejsz licznik / usuń
      wpis z ``APPROVED_FIRST``.
    """
    found = _scan(PATTERN_FIRST)

    nowe = {f: n for f, n in found.items() if n > APPROVED_FIRST.get(f, 0)}
    assert not nowe, (
        "Nowe/dodatkowe Uczelnia.objects.first()/all()[0] poza whitelistą "
        f"(potencjalny bug multi-hosted): {nowe}. Użyj jawnej uczelni "
        "(uczelnia_dla_odczytu / get_for_request / argument / single-or-fail) "
        "albo dopisz do APPROVED_FIRST w tym pliku z uzasadnieniem."
    )
