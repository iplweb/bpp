"""Testy bramki ``manage.py baseline_check``.

Bramka, która nigdy nie zwraca błędu, jest gorsza niż jej brak — świeci się
na zielono także wtedy, gdy ``baseline.sql`` realnie odjechał. Dlatego
ścieżka „przekroczony próg" jest tu testowana na równi ze ścieżką pogodną.

``check_freshness`` i ``get_config`` są podmieniane, żeby test mierzył
logikę bramki, a nie akurat stan ``baseline.meta.json`` w repo (ten zmienia
się przy każdym odświeżeniu baseline'u i uczyniłby test kruchym).
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@dataclass
class FakeRaport:
    deltas: dict
    worst_app: str
    worst_delta: int
    git_sha: str = "deadbeef"
    meta: dict = field(default_factory=dict)


@dataclass
class FakeConfig:
    meta_path: Path


@pytest.fixture
def podmien(monkeypatch, tmp_path):
    """Zwróć funkcję ustawiającą sztuczny raport świeżości."""
    meta = tmp_path / "baseline.meta.json"
    meta.write_text("{}")

    def ustaw(worst_delta, worst_app="bpp", meta_istnieje=True):
        if not meta_istnieje:
            sciezka = tmp_path / "nie-ma-mnie.json"
        else:
            sciezka = meta

        import django_pg_baseline.conf as conf
        import django_pg_baseline.freshness as freshness

        monkeypatch.setattr(conf, "get_config", lambda: FakeConfig(meta_path=sciezka))
        monkeypatch.setattr(
            freshness,
            "check_freshness",
            lambda _: FakeRaport(
                deltas={worst_app: worst_delta, "inna_app": 0},
                worst_app=worst_app,
                worst_delta=worst_delta,
            ),
        )

    return ustaw


def test_baseline_swiezy_przechodzi(podmien, capsys):
    podmien(worst_delta=3)
    call_command("baseline_check", "--max-delta", "50")
    assert "Baseline freshness OK." in capsys.readouterr().out


def test_delta_rowna_progowi_przechodzi(podmien, capsys):
    """Próg jest włączający — dokładnie --max-delta ma jeszcze przechodzić."""
    podmien(worst_delta=50)
    call_command("baseline_check", "--max-delta", "50")
    assert "Baseline freshness OK." in capsys.readouterr().out


def test_przekroczony_prog_zatrzymuje(podmien):
    """Sedno bramki: odjechany baseline MUSI wywalić komendę."""
    podmien(worst_delta=51, worst_app="pbn_api")
    with pytest.raises(CommandError) as wyjatek:
        call_command("baseline_check", "--max-delta", "50")
    komunikat = str(wyjatek.value)
    assert "pbn_api" in komunikat
    assert "+51" in komunikat
    # Komunikat ma prowadzić do właściwego targetu, nie do gołej komendy
    # Django (patrz CLAUDE.md: make dokłada fix-baseline-search-path).
    assert "make baseline-update" in komunikat


def test_domyslny_prog_to_50(podmien):
    podmien(worst_delta=51)
    with pytest.raises(CommandError):
        call_command("baseline_check")


def test_brak_meta_json_to_blad_z_instrukcja(podmien):
    podmien(worst_delta=0, meta_istnieje=False)
    with pytest.raises(CommandError) as wyjatek:
        call_command("baseline_check")
    assert "rebuild-baseline" in str(wyjatek.value)
