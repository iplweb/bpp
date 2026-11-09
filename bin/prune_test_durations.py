#!/usr/bin/env python
"""Usuń z `.test_durations` wpisy testów, których już nie ma.

pytest-split przy `--store-durations` MERGE'uje nowe czasy ze starym plikiem
(bez `--clean-durations`, bo `make tests` składa plik z dwóch przebiegów:
`not playwright` + `playwright` — patrz komentarz przy STORE_DURATIONS
w Makefile). Skutek uboczny: wpisy testów usuniętych lub przemianowanych
zostają w pliku na zawsze (2026-11: 274 martwe wpisy, w tym jeden
z zapisanymi 115,8 s). Nie psują splitu (pytest-split patrzy tylko na
zebrane testy), ale zaśmiecają plik i mylą przy jego czytaniu.

Skrypt zbiera node-id przez `pytest --collect-only -q` (pełna suita, oba
markery — bez `-m`) i zostawia tylko istniejące wpisy. Kolejność i wartości
bez zmian (plik jest już znormalizowany przez normalize_test_durations.py).
"""

import json
import subprocess
import sys
from pathlib import Path


def collected_nodeids() -> set[str]:
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:randomly",
            "--no-testcontainers",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ids = {line.strip() for line in out.stdout.splitlines() if "::" in line}
    if out.returncode != 0 or not ids:
        print(out.stdout[-2000:], out.stderr[-2000:], file=sys.stderr)
        raise SystemExit(
            "prune_test_durations: zbieranie testów nie powiodło się — "
            "plik zostaje bez zmian"
        )
    return ids


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".test_durations")
    data = json.loads(path.read_text())
    ids = collected_nodeids()
    kept = {k: v for k, v in data.items() if k in ids}
    removed = len(data) - len(kept)
    path.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")
    print(
        f"prune_test_durations: {len(kept)} wpisów, usunięto {removed} "
        f"nieistniejących testów → {path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
