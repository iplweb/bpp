#!/usr/bin/env python
"""``manage.py`` podpięte do bazy DZIAŁAJĄCEGO ``run-site``.

    uv run bin/run-site-manage.py shell
    uv run bin/run-site-manage.py pbn_konfiguracja_z_serwera LOGIN@HOST
    uv run bin/run-site-manage.py pbn_bezpiecznik_lokalnej_kopii --tak-to-jest-lokalna-kopia

Po co: ``run-site`` stawia PostgreSQL i Redisa na losowych portach. Plik
``.run-site-env.sh`` eksportuje ``DATABASE_URL`` / ``PG*``, ale ustawienia BPP
czytają ``DJANGO_BPP_DB_*`` — więc ``source .run-site-env.sh && python
src/manage.py …`` łączy się z ``localhost:5432`` i pada. Ten skrypt bierze
połączenia z ``.run-site-config`` (plik istnieje, dopóki run-site działa)
i ustawia właściwe zmienne — te same, które run-site podaje swoim
podprocesom (sekcja ``[env]`` w ``runsite.toml``).
"""

import os
import sys
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parent.parent
SIDECAR = REPO / ".run-site-config"


def srodowisko_z_run_site() -> dict:
    """Zmienne środowiskowe połączenia z bazą/Redisem działającego run-site."""
    try:
        konfiguracja = tomllib.loads(SIDECAR.read_text())
    except FileNotFoundError:
        sys.exit(
            f"Brak {SIDECAR} — lokalna instancja nie działa. Uruchom najpierw "
            "`uv run run-site run` w tym checkoucie."
        )
    pg = konfiguracja.get("postgres")
    if not pg:
        sys.exit(f"{SIDECAR} nie opisuje bazy PostgreSQL — nieobsługiwany tryb.")

    env = {
        "DJANGO_BPP_SKIP_DOTENV": "1",
        "DJANGO_BPP_DB_HOST": str(pg["host"]),
        "DJANGO_BPP_DB_PORT": str(pg["port"]),
        "DJANGO_BPP_DB_NAME": str(pg["db"]),
        "DJANGO_BPP_DB_USER": str(pg["user"]),
        "DJANGO_BPP_DB_PASSWORD": str(pg["password"]),
    }
    redis = konfiguracja.get("redis")
    if redis:
        env["DJANGO_BPP_REDIS_HOST"] = str(redis["host"])
        env["DJANGO_BPP_REDIS_PORT"] = str(redis["port"])
    return env


def main(argv):
    if not argv:
        sys.exit(__doc__)
    os.environ.update(srodowisko_z_run_site())
    sys.path.insert(0, str(REPO / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", *argv])


if __name__ == "__main__":
    main(sys.argv[1:])
