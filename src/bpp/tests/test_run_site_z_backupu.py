"""``bin/run-site-z-backupu.py`` — backup pg_dump w dowolnym formacie → plik
SQL, który ``run-site --from-dump`` ładuje bez klienta PostgreSQL na hoście."""

import gzip
import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

SKRYPT = Path(__file__).resolve().parents[3] / "bin" / "run-site-z-backupu.py"


@pytest.fixture
def rsb(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("run_site_z_backupu", SKRYPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setattr(modul, "KATALOG_CACHE", tmp_path / "cache")
    return modul


@pytest.fixture
def katalog_dump(tmp_path):
    """Katalog jak z ``pg_dump -Fd``: toc.dat + pliki danych."""
    katalog = tmp_path / "zrodla" / "db-backup-20260101"
    katalog.mkdir(parents=True)
    (katalog / "toc.dat").write_bytes(b"PGDMP" + b"\x00" * 64)
    (katalog / "1234.dat.gz").write_bytes(gzip.compress(b"dane"))
    return katalog


@pytest.fixture
def tar_gz(katalog_dump):
    """Nocny backup z bpp-deploy: tar.gz z katalogiem w środku."""
    archiwum = katalog_dump.parent / "db-backup-20260101.tar.gz"
    with tarfile.open(archiwum, "w:gz") as tar:
        tar.add(katalog_dump, arcname=katalog_dump.name)
    return archiwum


def _udawany_pg_restore(wywolania):
    """Zamiast Dockera: zapisz plik wyniku tam, gdzie zrobiłby to pg_restore."""

    def run(argv, check):
        wywolania.append(argv)
        montowania = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
        katalog_wyniku = Path(montowania[1].split(":")[0])
        nazwa = Path(argv[argv.index("-f") + 1]).name
        zrodlo = Path(montowania[0].split(":")[0])
        assert (zrodlo / "toc.dat").is_file() or zrodlo.is_file()
        (katalog_wyniku / nazwa).write_text("-- SQL z pg_restore\n")
        return subprocess.CompletedProcess(argv, 0)

    return run


def test_rozpoznaje_formaty(rsb, tmp_path, katalog_dump, tar_gz):
    sql = tmp_path / "a.sql"
    sql.write_text("CREATE TABLE x();")
    sql_gz = tmp_path / "a.sql.gz"
    sql_gz.write_bytes(gzip.compress(b"CREATE TABLE x();"))
    custom = tmp_path / "a.pg_dump"
    custom.write_bytes(b"PGDMP\x01\x10")
    tar = tmp_path / "a.tar"
    with tarfile.open(tar, "w") as t:
        t.add(katalog_dump, arcname="d")

    assert rsb.rozpoznaj(sql) == "sql"
    assert rsb.rozpoznaj(sql_gz) == "sql"
    assert rsb.rozpoznaj(custom) == "custom"
    assert rsb.rozpoznaj(katalog_dump) == "katalog"
    assert rsb.rozpoznaj(tar_gz) == "tar"
    assert rsb.rozpoznaj(tar) == "tar"


def test_bledy_wejscia(rsb, tmp_path):
    with pytest.raises(rsb.BladBackupu, match="Nie ma takiego pliku"):
        rsb.rozpoznaj(tmp_path / "nie-ma")
    pusty = tmp_path / "pusty"
    pusty.mkdir()
    with pytest.raises(rsb.BladBackupu, match="bez pliku toc.dat"):
        rsb.rozpoznaj(pusty)


def test_sql_idzie_bez_konwersji(rsb, tmp_path):
    sql = tmp_path / "a.sql.gz"
    sql.write_bytes(gzip.compress(b"SELECT 1;"))
    with patch.object(rsb.subprocess, "run") as run:
        assert rsb.przygotuj_dump(sql) == sql
    run.assert_not_called()


def test_tar_gz_z_katalogiem_jest_rozpakowywany_i_konwertowany(rsb, tar_gz):
    wywolania = []
    with patch.object(rsb.subprocess, "run", _udawany_pg_restore(wywolania)):
        wynik = rsb.przygotuj_dump(tar_gz, komunikat=lambda t: None)

    assert wynik.suffix == ".sql"
    assert wynik.parent == rsb.KATALOG_CACHE
    assert wynik.read_text() == "-- SQL z pg_restore\n"
    (argv,) = wywolania
    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv[argv.index("--entrypoint") + 1] == "pg_restore"
    assert "--no-owner" in argv and "--no-privileges" in argv
    assert argv[argv.index("--network") + 1] == "none"
    # Źródło montowane tylko do odczytu.
    assert argv[argv.index("-v") + 1].endswith(":/we/backup:ro")
    # Po konwersji w cache zostaje wyłącznie wynik (bez rozpakowanego katalogu).
    assert [p.name for p in rsb.KATALOG_CACHE.iterdir()] == [wynik.name]


def test_rozpakowany_katalog_tez_dziala(rsb, katalog_dump):
    wywolania = []
    with patch.object(rsb.subprocess, "run", _udawany_pg_restore(wywolania)):
        wynik = rsb.przygotuj_dump(katalog_dump, komunikat=lambda t: None)

    assert wynik.is_file()
    assert wywolania[0][wywolania[0].index("-v") + 1].startswith(str(katalog_dump))


def test_druga_konwersja_bierze_wynik_z_cache_a_zmieniony_backup_nie(rsb, tar_gz):
    wywolania = []
    with patch.object(rsb.subprocess, "run", _udawany_pg_restore(wywolania)):
        pierwszy = rsb.przygotuj_dump(tar_gz, komunikat=lambda t: None)
        drugi = rsb.przygotuj_dump(tar_gz, komunikat=lambda t: None)
        assert drugi == pierwszy
        assert len(wywolania) == 1

        # Nowy backup pod tą samą nazwą (inny rozmiar) → nowa konwersja.
        with tar_gz.open("ab") as f:
            f.write(b"\x00" * 1024)
        trzeci = rsb.przygotuj_dump(tar_gz, komunikat=lambda t: None)
    assert trzeci != pierwszy
    assert len(wywolania) == 2


def test_nieudany_pg_restore_nie_zostawia_polproduktu(rsb, katalog_dump):
    def pada(argv, check):
        katalog_wyniku = Path(argv[argv.index("-v") + 3].split(":")[0])
        (katalog_wyniku / Path(argv[argv.index("-f") + 1]).name).write_text("pol")
        raise subprocess.CalledProcessError(1, argv)

    with patch.object(rsb.subprocess, "run", pada):
        with pytest.raises(rsb.BladBackupu, match="pg_restore zakończył się kodem 1"):
            rsb.przygotuj_dump(katalog_dump, komunikat=lambda t: None)

    assert list(rsb.KATALOG_CACHE.glob("*.sql*")) == []


def test_main_przekazuje_reszte_argumentow_do_run_site(rsb, tmp_path):
    sql = tmp_path / "a.sql"
    sql.write_text("SELECT 1;")

    with patch.object(rsb.os, "execv") as execv, patch.object(rsb.os, "chdir"):
        rsb.main([str(sql), "--no-browser", "--get-pbn-token-from", "admin@serwer"])

    assert execv.call_args.args == (
        sys.executable,
        [
            sys.executable, "-m", "run_site", "run", "--from-dump", str(sql),
            "--no-browser", "--get-pbn-token-from", "admin@serwer",
        ],
    )  # fmt: skip


def test_tylko_konwersja_wypisuje_sama_sciezke(rsb, tmp_path, capsys):
    sql = tmp_path / "a.sql"
    sql.write_text("SELECT 1;")

    with patch.object(rsb.os, "execv") as execv:
        rsb.main([str(sql), "--tylko-konwersja"])

    execv.assert_not_called()
    assert capsys.readouterr().out.strip() == str(sql)


def test_obraz_bazy_z_runsite_toml(rsb):
    assert rsb.obraz_bazy().startswith("iplweb/bpp_dbserver:")
