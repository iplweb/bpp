"""Najlepsza liczba workerow xdist zmierzona na TEJ maszynie.

Plik ``.pytest-xdist-bench.json`` (gitignored, w korzeniu repo) zapisuje
``bin/xdist_bench.py`` (``make xdist-bench``). Hook
``pytest_xdist_auto_num_workers`` w rootdir-owym ``conftest.py`` przycina nim
``-n auto``: pytest-xdist-memory liczy, ile workerow zmiesci RAM, a tu
dokladamy gorny limit z benchmarku -- powyzej niego dodatkowe workery tylko
dziela te same rdzenie (np. SMT na Ryzenie: 16 i 24 workery = ten sam czas).

Modul MUSI byc wolny od Django -- importuje go rootdir-owy conftest
(patrz ``fixtures/__init__.py``).
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

import psutil

BENCH_FILENAME = ".pytest-xdist-bench.json"
VERSION = 1


def suite_key(markexpr: str | None) -> str:
    """Ten sam klucz co pytest-xdist-memory (``profile.suite_key``)."""
    return (markexpr or "").strip() or "default"


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except FileNotFoundError:
        pass  # macOS / brak procfs -- ponizej sysctl
    if sys.platform == "darwin":
        out = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout.strip():
            return out.stdout.strip()
    return platform.processor() or "unknown"


def fingerprint() -> dict:
    """Co musi sie zgadzac, zeby wynik benchmarku dotyczyl tej maszyny."""
    return {
        "hostname": platform.node(),
        "cpu_model": cpu_model(),
        "logical_cpus": psutil.cpu_count(logical=True),
        "physical_cpus": psutil.cpu_count(logical=False),
    }


def empty() -> dict:
    return {"version": VERSION, "fingerprint": fingerprint(), "suites": {}}


def load(path: Path) -> tuple[dict, str | None]:
    """Zwraca (dane, powod_odrzucenia). Obcy/uszkodzony plik -> puste dane."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return empty(), None
    except (OSError, ValueError) as exc:
        return empty(), f"nieczytelny ({exc})"
    if data.get("version") != VERSION:
        return empty(), "inna wersja formatu"
    if data.get("fingerprint") != fingerprint():
        return empty(), "z innej maszyny (hostname/CPU)"
    return data, None


def best_workers(rootdir: Path, markexpr: str | None) -> tuple[int | None, str]:
    """Najlepsze ``-n`` dla tego ``-m`` albo (None, powod)."""
    path = rootdir / BENCH_FILENAME
    data, problem = load(path)
    if problem:
        return None, f"{BENCH_FILENAME} {problem} -- pomijam"
    suite = data["suites"].get(suite_key(markexpr))
    if not suite:
        return None, ""
    return int(suite["best"]), f"z {BENCH_FILENAME}, pomiar {suite['measured_at']}"


# --- Pamięć: model i rekomendacje (bin/xdist_bench.py --show) -------------

#: Rozmiary RAM (GB), dla których ``--show`` podaje maksymalne ``-n``.
TYPOWE_RAM_GB = (8, 16, 32, 64, 128)

#: Zapas RAM-u na system i resztę maszyny przy rekomendacjach (MB).
REZERWA_MB = 2048


def dopasuj_pamiec(punkty: list[tuple[int, float]]) -> tuple[float, float] | None:
    """Model ``szczyt_MB ≈ stała + na_workera × n`` (najmniejsze kwadraty)
    z punktów ``(n, szczyt_MB)``. Jeden punkt (albo jedno ``n``) → całość
    na workera, stała 0. ``None`` bez punktów."""
    punkty = [(n, mb) for n, mb in punkty if mb is not None and n > 0]
    if not punkty:
        return None
    ns = {n for n, _ in punkty}
    if len(ns) == 1:
        n, mb = max(punkty, key=lambda p: p[1])
        return 0.0, mb / n
    k = len(punkty)
    sx = sum(n for n, _ in punkty)
    sy = sum(mb for _, mb in punkty)
    sxx = sum(n * n for n, _ in punkty)
    sxy = sum(n * mb for n, mb in punkty)
    na_workera = (k * sxy - sx * sy) / (k * sxx - sx * sx)
    stala = (sy - na_workera * sx) / k
    if na_workera <= 0:  # szum pomiaru — przyjmij średni koszt na workera
        na_workera = max(mb / n for n, mb in punkty)
        stala = 0.0
    return max(stala, 0.0), na_workera


def max_workers_dla_ram(
    ram_mb: float, model: tuple[float, float], rezerwa_mb: float = REZERWA_MB
) -> int:
    """Ile workerów zmieści ``ram_mb`` wg modelu (z zapasem na system)."""
    stala, na_workera = model
    return max(int((ram_mb - rezerwa_mb - stala) // na_workera), 0)


def czas_dla_n(tabela: list[dict], n: int) -> float | None:
    """Zmierzony czas (mediana) dla największego zmierzonego ``-n`` ≤ ``n``
    — szacunek z dołu dla maszyny, która zmieści ``n`` workerów."""
    ok = [w for w in tabela if w.get("ok") and w["n"] <= n]
    if not ok:
        return None
    return max(ok, key=lambda w: w["n"])["median_wall_s"]


def rekomendacje(suite: dict, fp: dict) -> list[str]:
    """Wymagania sprzętowe z pomiaru: ile RAM-u przy najlepszym ``-n`` i ile
    workerów (z jakim czasem) zmieści się przy typowych rozmiarach RAM."""
    tabela = suite.get("table", [])
    punkty = [
        (w["n"], w["peak_ram_mb"])
        for w in tabela
        if w.get("ok") and w.get("peak_ram_mb") is not None
    ]
    model = dopasuj_pamiec(punkty)
    if model is None:
        return ["  brak pomiaru pamięci — odpal benchmark ponownie (nowa wersja)"]
    best = suite["best"]
    stala, na_workera = model
    wiersz_best = next((w for w in tabela if w["n"] == best), None)
    szczyt_best = (wiersz_best or {}).get("peak_ram_mb")
    zmierzone = [w["n"] for w in tabela if w.get("ok")]
    if zmierzone and best < max(zmierzone):
        uwaga = "więcej workerów już nie przyspiesza"
    else:
        uwaga = (
            "to największe zmierzone -n — więcej workerów może jeszcze"
            " przyspieszyć, zmierz większe (XDIST_BENCH_CANDIDATES)"
        )
    linie = [
        f"  model RAM: ~{stala / 1024:.1f} GB stałe + {na_workera:.0f} MB na worker"
        " (procesy pytest + kontenery testcontainers)",
        f"  najszybciej: -n {best} ({fp['physical_cpus']} rdzeni fizycznych /"
        f" {fp['logical_cpus']} wątków); {uwaga}",
    ]
    if szczyt_best is not None:
        potrzeba = szczyt_best + REZERWA_MB
        linie.append(
            f"  pełna prędkość (-n {best}) wymaga ~{potrzeba / 1024:.0f} GB RAM"
            f" (szczyt {szczyt_best / 1024:.1f} GB + {REZERWA_MB // 1024} GB zapasu)"
        )
    for gb in TYPOWE_RAM_GB:
        n = min(max_workers_dla_ram(gb * 1024, model), best)
        if n < 1:
            linie.append(f"  {gb:>3} GB RAM: za mało nawet na 1 workera")
            continue
        czas = czas_dla_n(tabela, n)
        czas_txt = f", ~{czas:.0f} s lub dłużej" if czas is not None else ""
        if czas is not None and n == best:
            czas_txt = f", ~{czas:.0f} s"
        linie.append(f"  {gb:>3} GB RAM: -n {n}{czas_txt}")
    return linie
