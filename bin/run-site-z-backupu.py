#!/usr/bin/env python
"""``run-site`` na backupie bazy w DOWOLNYM formacie pg_dump.

    uv run bin/run-site-z-backupu.py ~/Backups/<katalog>/db-backup-<TS>.tar.gz
    uv run bin/run-site-z-backupu.py <backup> --get-pbn-token-from LOGIN@HOST
    uv run bin/run-site-z-backupu.py <backup> --tylko-konwersja   # wypisz ścieżkę .sql

Wszystko po ścieżce backupu idzie bez zmian do ``run-site run``.

Po co: nocny backup z ``bpp-deploy`` to ``db-backup-<TS>.tar.gz`` z KATALOGIEM
``pg_dump -Fd`` w środku (``toc.dat`` + ``*.dat.gz``). ``run-site --from-dump``
ładuje archiwa pg_dump klientem ``pg_restore``/``psql`` z HOSTA — gdy go nie
ma, kończy się „'psql' not found on PATH", a rozpakowany katalog podany
wprost daje ``IsADirectoryError``. Zwykły ``.sql`` run-site ładuje bez
klienta na hoście (skrypt startowy kontenera). Ten skrypt robi więc z backupu
plik ``.sql``, uruchamiając ``pg_restore`` w kontenerze z obrazu bazy
z ``runsite.toml`` — na hoście wystarcza Docker.

Wynik konwersji trafia do ``~/.cache/bpp/dumpy`` i jest używany ponownie,
dopóki plik źródłowy się nie zmieni. Pliki bywają duże (setki MB) — katalog
można bezpiecznie skasować.
"""

import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parent.parent
KATALOG_CACHE = Path.home() / ".cache" / "bpp" / "dumpy"

#: Pierwsze bajty archiwum pg_dump (format custom oraz ``toc.dat`` katalogu).
MAGIA_PGDUMP = b"PGDMP"
MAGIA_GZIP = b"\x1f\x8b"
PRZESUNIECIE_USTAR = 257


class BladBackupu(Exception):
    """Czytelny dla człowieka problem z plikiem backupu."""


def rozpoznaj(sciezka: Path) -> str:
    """``sql`` (run-site przyjmie wprost), ``katalog``, ``tar`` albo ``custom``."""
    if not sciezka.exists():
        raise BladBackupu(f"Nie ma takiego pliku ani katalogu: {sciezka}")
    if sciezka.is_dir():
        if not (sciezka / "toc.dat").is_file():
            raise BladBackupu(
                f"{sciezka} to katalog bez pliku toc.dat — nie wygląda na "
                "backup `pg_dump -Fd`."
            )
        return "katalog"
    with sciezka.open("rb") as f:
        poczatek = f.read(512)
    if poczatek.startswith(MAGIA_PGDUMP):
        return "custom"
    if poczatek[PRZESUNIECIE_USTAR : PRZESUNIECIE_USTAR + 5] == b"ustar":
        return "tar"
    if poczatek.startswith(MAGIA_GZIP):
        # .sql.gz albo .tar.gz — rozstrzyga zawartość, nie nazwa.
        try:
            with tarfile.open(sciezka, "r:gz") as tar:
                tar.next()
            return "tar"
        except tarfile.ReadError:
            return "sql"  # zwykły zgzipowany SQL
    return "sql"


def sciezka_wyniku(zrodlo: Path) -> Path:
    """Plik .sql w cache — nazwa zależy od rozmiaru i czasu modyfikacji
    źródła, więc nowy backup o tej samej nazwie nie trafi w stary wynik."""
    stat = zrodlo.stat()
    nazwa = zrodlo.name
    for koncowka in (".tar.gz", ".tgz", ".tar", ".pg_dump", ".pgdump", ".dump"):
        if nazwa.endswith(koncowka):
            nazwa = nazwa[: -len(koncowka)]
            break
    return KATALOG_CACHE / f"{nazwa}-{stat.st_size}-{int(stat.st_mtime)}.sql"


def katalog_z_toc(korzen: Path) -> Path:
    for toc in sorted(korzen.rglob("toc.dat")):
        return toc.parent
    raise BladBackupu(
        "W archiwum nie ma pliku toc.dat — to nie jest spakowany katalog `pg_dump -Fd`."
    )


def obraz_bazy() -> str:
    konfiguracja = tomllib.loads((REPO / "runsite.toml").read_text())
    return konfiguracja["postgres"]["image"]


def polecenie_pg_restore(zrodlo: Path, wynik_tmp: Path, obraz: str) -> list[str]:
    """``pg_restore`` w kontenerze: archiwum → zwykły SQL. Bez sieci, źródło
    tylko do odczytu, pliki wyniku jako bieżący użytkownik."""
    return [
        "docker", "run", "--rm", "--network", "none",
        "-u", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{zrodlo}:/we/backup:ro",
        "-v", f"{wynik_tmp.parent}:/wy",
        "--entrypoint", "pg_restore",
        obraz,
        "--no-owner", "--no-privileges",
        "-f", f"/wy/{wynik_tmp.name}",
        "/we/backup",
    ]  # fmt: skip


def _na_stderr(tekst):
    # stdout zostaje czysty dla --tylko-konwersja (sama ścieżka).
    print(tekst, file=sys.stderr)


def konwertuj(zrodlo: Path, rodzaj: str, komunikat=_na_stderr) -> Path:
    wynik = sciezka_wyniku(zrodlo)
    if wynik.is_file():
        komunikat(f"Używam wcześniejszej konwersji: {wynik}")
        return wynik

    KATALOG_CACHE.mkdir(parents=True, exist_ok=True)
    wynik_tmp = wynik.with_name(wynik.name + ".w-trakcie")
    with tempfile.TemporaryDirectory(dir=KATALOG_CACHE, prefix="rozpakowany-") as tmp:
        archiwum = zrodlo
        if rodzaj == "tar":
            komunikat(f"Rozpakowuję {zrodlo.name}…")
            with tarfile.open(zrodlo) as tar:
                tar.extractall(tmp, filter="data")
            archiwum = katalog_z_toc(Path(tmp))
        komunikat(f"Konwertuję backup na SQL (pg_restore w kontenerze {obraz_bazy()})…")
        try:
            subprocess.run(
                polecenie_pg_restore(archiwum.resolve(), wynik_tmp, obraz_bazy()),
                check=True,
            )
        except FileNotFoundError as e:
            raise BladBackupu("Nie znaleziono polecenia `docker`.") from e
        except subprocess.CalledProcessError as e:
            wynik_tmp.unlink(missing_ok=True)
            raise BladBackupu(
                f"pg_restore zakończył się kodem {e.returncode} — backup jest "
                "uszkodzony albo zrobiony nowszą wersją PostgreSQL niż obraz "
                "z runsite.toml."
            ) from e
    wynik_tmp.replace(wynik)
    komunikat(f"Gotowe: {wynik} ({wynik.stat().st_size / 1e6:.0f} MB)")
    return wynik


def przygotuj_dump(sciezka: Path, komunikat=_na_stderr) -> Path:
    """Ścieżka, którą ``run-site --from-dump`` przyjmie bez klienta PG na hoście."""
    rodzaj = rozpoznaj(sciezka)
    if rodzaj == "sql":
        return sciezka
    return konwertuj(sciezka, rodzaj, komunikat)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    reszta = argv[1:]
    try:
        dump = przygotuj_dump(Path(argv[0]).expanduser().resolve())
    except BladBackupu as e:
        sys.exit(f"BŁĄD: {e}")

    if "--tylko-konwersja" in reszta:
        print(dump)
        return
    os.chdir(REPO)
    os.execv(
        sys.executable,
        [sys.executable, "-m", "run_site", "run", "--from-dump", str(dump), *reszta],
    )


if __name__ == "__main__":
    main(sys.argv[1:])
