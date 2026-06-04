"""Guard multi-hosted: pilnuje, że ``Uczelnia.objects.get_default()`` /
``Uczelnia.objects.default`` nie pojawia się poza ZATWIERDZONĄ whitelistą.

Każdy wpis na whiteliście to ŚWIADOMA decyzja (świadomy fallback bez requestu,
None-tolerant warstwa modelu, parked TODO per-uczelnia, albo guarded count==1).
Nowe użycie ``get_default`` w ścieżce runtime to potencjalny bug multi-hosted —
zgaduje uczelnię „pierwszą-z-brzegu" zamiast użyć właściwej.

Gdy ten test PADA:
- DODAŁEŚ ``get_default``/``objects.default`` → użyj JAWNEJ uczelni:
  ``get_for_request(request)`` (widoki), argument przekazany od wołającego,
  albo FK na obiekcie (np. ``session.uczelnia``, wpis kolejki). Jeśli miejsce
  jest NAPRAWDĘ akceptowalne — dopisz je do ``APPROVED`` z uzasadnieniem.
- USUNĄŁEŚ ``get_default`` (np. naprawiłeś multi-hosted) → zmniejsz licznik
  albo usuń wpis z ``APPROVED``.

Patrz: docs/deweloper/audyt-multihosted-pbn.md
"""

import re
from pathlib import Path

# Wzorzec: faktyczne wywołania na managerze (NIE ``self.get_default()``
# w definicji UczelniaManager, które tego wzorca nie pasują).
PATTERN = re.compile(r"Uczelnia\.objects\.(?:get_default\(\)|default\b)")

# Drugi footgun, semantycznie równoważny ``get_default`` w ścieżce runtime:
# ``Uczelnia.objects.first()`` / ``Uczelnia.objects.all()[0]`` zgaduje
# „pierwszą-z-brzegu" uczelnię niezależnie od hosta (uczelni) z requestu —
# ta sama klasa buga co B1, inna pisownia. ``all()[0]`` dorzucony
# prewencyjnie (0 wystąpień dziś, zerowy koszt utrzymania).
PATTERN_FIRST = re.compile(r"Uczelnia\.objects\.(?:first\(\)|all\(\)\s*\[\s*0\s*\])")

SRC = Path(__file__).resolve().parents[2]  # .../src

# Ścieżka (względem src/) -> dozwolona liczba wystąpień. Komentarz = dlaczego OK.
APPROVED: dict[str, int] = {
    "bpp/middleware.py": 1,  # świadomy fallback: Site istnieje, brak Uczelni
    "bpp/util/bpp_specific.py": 2,  # docstring + świadomy fallback (CLI/Celery bez requestu)
    # bpp/models/sloty/core.py i abstract/disciplines.py: get_default USUNIĘTY
    # (per-uczelnia sloty zrealizowane — ISlot._rozstrzygnij_uczelnie + przelicz
    # bez parametru). Brak wpisu = guard złapie ewentualny powrót get_default.
    "bpp/models/abstract/pbn.py": 2,  # linki PBN, metoda modelu bez requestu
    "bpp/models/jednostka.py": 1,  # sortowanie (display), warstwa modelu
    # do_roku_default(request=None): default pola modelu (migracja
    # 0020_fix_do_roku_default_modulowa_funkcja) + initial= formularzy raportów.
    # Musi być request-less i serializowalny w migracji, więc świadomy
    # fallback get_default() z obsługą None (per-uczelnia override idzie przez
    # metodę managera do_roku_default(request=...) wyżej w pliku).
    "bpp/models/uczelnia.py": 1,
    "bpp/multiseek_registry/fields/numeric_fields.py": 1,  # toggle IC, None-tolerant
    "ewaluacja2021/util.py": 1,  # komentarz (nie kod)
    "pbn_api/management/commands/util.py": 1,  # GUARDED count==1 (wzorzec CLI)
    "pbn_import/templatetags/pbn_import_tags.py": 1,  # request-first, fallback bez requestu
    "pbn_import/utils/command_helpers.py": 1,  # CLI None-tolerant + CommandError
}

# Whitelist dla ``Uczelnia.objects.first()``. Każdy wpis to ŚWIADOMY fallback
# bez requestu (warstwa modelu / UI default / demo / debug / komentarz).
APPROVED_FIRST: dict[str, int] = {
    "bpp/admin/core.py": 1,  # admin form __init__: default pola 'afiliuje', None-tolerant UI
    "bpp/demo_data/generators/uczelnia.py": 1,  # demo/seed, CLI bez requestu
    "bpp/management/commands/debug_setup_initial_data.py": 1,  # debug command, None-tolerant
    "bpp/models/autor.py": 1,  # warstwa modelu: domyślne 'pokazuj' nowego autora, None-tolerant
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


def test_get_default_poza_whitelista_to_regresja_multihosted():
    found = _scan(PATTERN)

    nowe = {f: n for f, n in found.items() if n > APPROVED.get(f, 0)}
    assert not nowe, (
        "Nowe/dodatkowe Uczelnia.objects.get_default()/.default poza whitelistą "
        f"(potencjalny bug multi-hosted): {nowe}. Użyj jawnej uczelni "
        "(get_for_request / argument / FK obiektu) albo dopisz do APPROVED "
        "w tym pliku z uzasadnieniem."
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
