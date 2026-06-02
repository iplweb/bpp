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
    "bpp/multiseek_registry/fields/numeric_fields.py": 1,  # toggle IC, None-tolerant
    "ewaluacja2021/util.py": 1,  # komentarz (nie kod)
    "pbn_api/adapters/wydawnictwo.py": 1,  # test-only None-tolerant fallback
    "pbn_api/management/commands/util.py": 1,  # GUARDED count==1 (wzorzec CLI)
    "pbn_import/templatetags/pbn_import_tags.py": 1,  # request-first, fallback bez requestu
    "pbn_import/utils/command_helpers.py": 1,  # CLI None-tolerant + CommandError
    "pbn_integrator/importer/authors.py": 5,  # TODO integrator per-uczelnia (parked)
    "pbn_integrator/utils/scientists.py": 1,  # TODO integrator per-uczelnia (parked)
    "pbn_integrator/management/commands/pbn_integrator.py": 1,  # TODO integrator per-uczelnia
    "powiazania_autorow/queries.py": 1,  # dev: explorer, root PBN raz (anty-N+1), display; deferred multi-host
}


def _scan() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if "/tests/" in f"/{rel}" or "/migrations/" in f"/{rel}":
            continue
        if path.name.startswith("test_"):
            continue
        n = len(PATTERN.findall(path.read_text(encoding="utf-8")))
        if n:
            found[rel] = n
    return found


def test_get_default_poza_whitelista_to_regresja_multihosted():
    found = _scan()

    nowe = {f: n for f, n in found.items() if n > APPROVED.get(f, 0)}
    assert not nowe, (
        "Nowe/dodatkowe Uczelnia.objects.get_default()/.default poza whitelistą "
        f"(potencjalny bug multi-hosted): {nowe}. Użyj jawnej uczelni "
        "(get_for_request / argument / FK obiektu) albo dopisz do APPROVED "
        "w tym pliku z uzasadnieniem."
    )
