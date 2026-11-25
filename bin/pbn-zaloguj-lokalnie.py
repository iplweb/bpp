#!/usr/bin/env python
"""Jedno polecenie: działający token PBN w LOKALNEJ instancji BPP.

    uv run bin/pbn-zaloguj-lokalnie.py                       # logowanie w PBN
    uv run bin/pbn-zaloguj-lokalnie.py --konfiguracja-z HOST # + konfiguracja z serwera
    uv run bin/pbn-zaloguj-lokalnie.py --ott <kod>           # awaryjnie, bez przeglądarki
    uv run bin/pbn-zaloguj-lokalnie.py --tylko-sprawdz

Wymaga działającego ``uv run run-site run`` w tym samym checkoucie: z jego
pliku ``.run-site-config`` bierze adres strony oraz połączenie z bazą
i Redisem, po czym woła ``manage.py pbn_zaloguj_lokalnie`` (tam cała logika
i wszystkie opcje: ``--help``).

Opis: docs/deweloper/testowanie-pbn-lokalnie.md
"""

import os
import sys
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parent.parent
SIDECAR = REPO / ".run-site-config"


def _srodowisko_z_run_site() -> str:
    """Ustawia zmienne połączenia z bazą/Redisem run-site. Zwraca adres strony."""
    try:
        konfiguracja = tomllib.loads(SIDECAR.read_text())
    except FileNotFoundError:
        sys.exit(
            f"Brak {SIDECAR} — lokalna instancja nie działa. Uruchom najpierw "
            "`uv run run-site run --from-dump <plik>` w tym checkoucie."
        )
    pg = konfiguracja.get("postgres")
    if not pg:
        sys.exit(f"{SIDECAR} nie opisuje bazy PostgreSQL — nieobsługiwany tryb.")

    os.environ.update(
        {
            # run-site ustawia to samo swoim podprocesom ([env] w runsite.toml).
            "DJANGO_BPP_SKIP_DOTENV": "1",
            "DJANGO_BPP_DB_HOST": str(pg["host"]),
            "DJANGO_BPP_DB_PORT": str(pg["port"]),
            "DJANGO_BPP_DB_NAME": str(pg["db"]),
            "DJANGO_BPP_DB_USER": str(pg["user"]),
            "DJANGO_BPP_DB_PASSWORD": str(pg["password"]),
        }
    )
    redis = konfiguracja.get("redis")
    if redis:
        os.environ["DJANGO_BPP_REDIS_HOST"] = str(redis["host"])
        os.environ["DJANGO_BPP_REDIS_PORT"] = str(redis["port"])
    return str(konfiguracja["web"]["url"]).rstrip("/")


def main(argv):
    url = _srodowisko_z_run_site()
    if not any(a == "--url" or a.startswith("--url=") for a in argv):
        argv = ["--url", url, *argv]

    sys.path.insert(0, str(REPO / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "pbn_zaloguj_lokalnie", *argv])


if __name__ == "__main__":
    main(sys.argv[1:])
