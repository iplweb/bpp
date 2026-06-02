#!/usr/bin/env python
"""Normalizuj `.test_durations` po `pytest --store-durations`.

pytest-split zapisuje czasy z pelna precypcja floata
(`0.05623337556608021`) w kolejnosci zbierania — przez co KAZDY
`make tests` przepisuje wszystkie 4000+ wartosci i produkuje ogromny,
szumny diff, nawet gdy czasy ledwie drgnely.

Ten skrypt:
  * zaokragla czasy do 3 miejsc (1 ms — i tak grubo ponizej rozdzielczosci
    istotnej dla balansu grup po ~380 s; ale 3 miejsca zachowuja sume
    tysiecy mikro-testow, czego 2 miejsca by nie zrobily),
  * sortuje klucze (stabilna kolejnosc → diff pokazuje tylko realnie
    zmienione testy),
  * konczy plik newline'em.

Dzieki temu regeneracja przez `make tests` daje maly, czytelny diff.
CI pliku nie dotyka — czyta go read-only (docker-compose.test.ci.yml).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROUND_NDIGITS = 3


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".test_durations")
    if not path.is_file():
        print(f"normalize_test_durations: brak {path}", file=sys.stderr)
        return 1

    raw = json.loads(path.read_text())
    normalized = {
        key: round(float(value), ROUND_NDIGITS)
        for key, value in sorted(raw.items())
    }
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")
    print(f"normalize_test_durations: {len(normalized)} wpisow → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
