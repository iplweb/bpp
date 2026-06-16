#!/usr/bin/env python
"""Normalizuj `.test_durations` po `pytest --store-durations`.

pytest-split zapisuje czasy z pelna precyzja floata
(`0.05623337556608021`) w kolejnosci zbierania. Samo zaokraglenie do 3
miejsc + sort nie wystarcza: realny szum pomiarow (obciazenie maszyny,
cache, kolejnosc) jest DUZO wiekszy niz 1 ms — typowy `make tests`
przepisuje ~83% z 4000+ wartosci (`5.012 → 2.807`, `1.228 → 0.72`),
produkujac ogromny, nieczytelny diff. Grubsze zaokraglanie pomaga slabo
(środkowy zakres przeskakuje kazda stala dzialke) i psuje precyzje.

Dlatego stosujemy HISTEREZE wzgledem zacommitowanego baseline'u
(`git show HEAD:.test_durations`): wartosc nadpisujemy TYLKO gdy zmiana
jest istotna — wzglednie (> `REL_THRESHOLD`) **i** bezwzglednie
(> `ABS_THRESHOLD`). Drobne drgniecia zostaja przy starej wartosci, wiec
diff pokazuje wylacznie testy, ktorych czas faktycznie sie zmienil
(~16-32% zamiast 83%), bez zadnej utraty precyzji dla tych zmienionych.

To bezpieczne, bo plik sluzy tylko `pytest-split` do balansu shardow CI
(relatywne wagi, suma ~kilka tys. s na ~12 grup). „Stale" 0.04 vs 0.05
albo 5 s test odswiezony z opoznieniem zmienia podzial o ulamek procenta.

Skrypt:
  * zaokragla nowe czasy do 3 miejsc (1 ms),
  * stosuje histereze wzgledem baseline'u z HEAD (nowe/usuniete testy
    przechodza wprost),
  * sortuje klucze (stabilna kolejnosc → minimalny diff),
  * konczy plik newline'em.

Fallback: gdy baseline'u nie da sie odczytac (plik nie w HEAD, brak repo,
pierwszy zapis) — degraduje do samego round(3) + sort, jak poprzednio.
CI pliku nie dotyka — czyta go read-only (docker-compose.test.ci.yml).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROUND_NDIGITS = 3
# Nadpisz wartosc tylko gdy zmiana przekracza OBA progi naraz.
REL_THRESHOLD = 0.20  # >20% wzglednej zmiany
ABS_THRESHOLD = 0.015  # >15 ms bezwzglednej zmiany


def load_baseline(path: Path) -> dict[str, float] | None:
    """Zacommitowana wersja pliku z HEAD, albo None gdy niedostepna."""
    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{path.as_posix()}"],
            capture_output=True,
            text=True,
            check=True,
            cwd=path.parent if path.parent != Path("") else None,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        # Brak repo / pliku w HEAD / gita — histereza nieosiagalna,
        # degradujemy do czystego round+sort. To nie blad: pierwszy
        # zapis pliku albo detached state przechodzi ta sciezka.
        print(
            f"normalize_test_durations: baseline niedostepny "
            f"({exc.__class__.__name__}) — bez histerezy",
            file=sys.stderr,
        )
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        print(
            f"normalize_test_durations: baseline z HEAD nieparsowalny "
            f"({exc}) — bez histerezy",
            file=sys.stderr,
        )
        return None


def is_significant(new: float, base: float) -> bool:
    """Czy zmiana new vs base przekracza oba progi (wzgl. i bezwzgl.)?"""
    diff = abs(new - base)
    if diff <= ABS_THRESHOLD:
        return False
    if base == 0:
        return True  # z zera na cokolwiek > ABS_THRESHOLD to istotna zmiana
    return diff / base > REL_THRESHOLD


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".test_durations")
    if not path.is_file():
        print(f"normalize_test_durations: brak {path}", file=sys.stderr)
        return 1

    raw = json.loads(path.read_text())
    baseline = load_baseline(path)

    result: dict[str, float] = {}
    kept = updated = added = 0
    for key, value in sorted(raw.items()):
        new = round(float(value), ROUND_NDIGITS)
        if baseline is None or key not in baseline:
            result[key] = new
            added += baseline is not None and key not in baseline
            continue
        base = baseline[key]
        if is_significant(new, base):
            result[key] = new
            updated += 1
        else:
            result[key] = base  # histereza: trzymaj stara wartosc
            kept += 1

    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    if baseline is None:
        print(f"normalize_test_durations: {len(result)} wpisow → {path}")
    else:
        print(
            f"normalize_test_durations: {len(result)} wpisow → {path} "
            f"(stabilne: {kept}, zaktualizowane: {updated}, nowe: {added})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
