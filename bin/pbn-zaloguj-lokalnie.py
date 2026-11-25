#!/usr/bin/env python
"""Jedno polecenie: działający token PBN w LOKALNEJ instancji BPP.

    uv run bin/pbn-zaloguj-lokalnie.py                       # logowanie w PBN
    uv run bin/pbn-zaloguj-lokalnie.py --uczelnia SKROT      # gdy uczelni jest kilka
    uv run bin/pbn-zaloguj-lokalnie.py --konfiguracja-z HOST # + konfiguracja z serwera
    uv run bin/pbn-zaloguj-lokalnie.py --ott <kod>           # awaryjnie, bez przeglądarki
    uv run bin/pbn-zaloguj-lokalnie.py --tylko-sprawdz

Wymaga działającego ``uv run run-site run`` w tym samym checkoucie. To skrót
do ``bin/run-site-manage.py pbn_zaloguj_lokalnie …`` — tam jest podpięcie do
bazy run-site, a cała logika i opcje (``--help``) siedzą w komendzie.

Opis: docs/deweloper/testowanie-pbn-lokalnie.md
"""

import os
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent / "run-site-manage.py"

if __name__ == "__main__":
    os.execv(
        sys.executable,
        [sys.executable, str(LAUNCHER), "pbn_zaloguj_lokalnie", *sys.argv[1:]],
    )
