#!/usr/bin/env python
"""Ile workerow xdist zmiesci sie w RAM-ie tej maszyny.

Na maszynie interaktywnej (laptop z pulpitem) waskim gardlem testow jest
pamiec, nie CPU: `pytest -n auto` na 14 rdzeniach / 14 GB RAM wpedzil
system w thrashing swapu i wymagal twardego resetu. Workery xdist ROSNA
w trakcie przebiegu, jesli GC nie sprzata cykli referencji (zmierzone bez
okresowego ``gc.collect()``: 400 MB -> 1,75 GB w 3 minuty; z nim, patrz
pytest-gc-steward w pytest.ini: ~450-650 MB). Kazdy worker
doklada tez backend PostgreSQL w testcontainerze.

Podkomendy:

    measure  -- puszcza probke testow z `-n 2`, probkuje RSS drzewa
                procesow pytest i PG w kontenerze, zapisuje profil do
                `.xdist-mem-profile.json` (gitignored, per maszyna).
    calc     -- z profilu + aktualnie dostepnej pamieci liczy bezpieczne
                `-n`. `--quiet` drukuje sama liczbe (dla Makefile).
    guard    -- drukuje prefiks `systemd-run ... MemoryMax=...` (Linux),
                zeby przekroczenie zabilo testy, a nie zamrozilo maszyne.
                Pusty wynik, gdy systemd-run niedostepny (np. macOS).

Zmienne srodowiskowe:

    XDIST_RESERVE_MB  -- ile MB zostawic dla pulpitu/systemu (domyslnie 2048)
    XDIST_SAFETY      -- mnoznik zapasu na szczyt workera (domyslnie 1.25)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parent.parent
PROFILE = REPO / ".xdist-mem-profile.json"
MB = 1024 * 1024

# Domyslne wartosci, gdy nie ma profilu -- z pomiaru 2026-11-05 na
# thinkpad14s (src/bpp/tests/test_{models,admin,views}, -n 4, z okresowym
# gc.collect() w src/conftest.py).
DEFAULT_WORKER_MB = 640
DEFAULT_CONTROLLER_MB = 230
DEFAULT_PG_PER_WORKER_MB = 150

DEFAULT_SAMPLE_PATHS = [
    "src/bpp/tests/test_models",
    "src/bpp/tests/test_admin",
    "src/bpp/tests/test_views",
]


def _reserve_mb() -> int:
    return int(os.environ.get("XDIST_RESERVE_MB", "2048"))


def _safety() -> float:
    return float(os.environ.get("XDIST_SAFETY", "1.25"))


def _available_mb() -> int:
    return psutil.virtual_memory().available // MB


def _classify(proc: psutil.Process) -> str:
    try:
        cmd = " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "other"
    # execnet startuje workery jako `python -c "...exec(eval(...))"`.
    if "exec(eval(" in cmd or "execnet" in cmd:
        return "worker"
    if "pytest" in cmd:
        return "controller"
    return "other"


def _docker_pg_mb(known: set[str]) -> int | None:
    """RSS nowych (powstalych w trakcie pomiaru) kontenerow tc-psql."""
    if not shutil.which("docker"):
        return None
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}}"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
    except subprocess.TimeoutExpired:
        return None
    total = None
    for line in out.splitlines():
        name, _, usage = line.partition(" ")
        if "tc-psql" not in name or name in known:
            continue
        used = usage.split("/")[0].strip()
        for unit, mult in (("GiB", 1024), ("MiB", 1), ("KiB", 1 / 1024)):
            if used.endswith(unit):
                total = (total or 0) + int(float(used[: -len(unit)]) * mult)
                break
    return total


def _docker_pg_names() -> set[str]:
    if not shutil.which("docker"):
        return set()
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    ).stdout
    return {n for n in out.split() if "tc-psql" in n}


def guard_prefix(limit_mb: int) -> list[str]:
    if not sys.platform.startswith("linux") or not shutil.which("systemd-run"):
        return []
    probe = subprocess.run(
        ["systemd-run", "--user", "--scope", "-q", "true"], capture_output=True
    )
    if probe.returncode != 0:
        return []
    return [
        "systemd-run",
        "--user",
        "--scope",
        "-q",
        "-p",
        f"MemoryMax={limit_mb}M",
        "-p",
        "MemorySwapMax=0",
    ]


def cmd_measure(args) -> int:
    workers = args.workers
    pg_before = _docker_pg_names()
    limit = max(_available_mb() - _reserve_mb(), 1024)
    cmd = guard_prefix(limit) + [
        "uv",
        "run",
        "pytest",
        "-n",
        str(workers),
        "-m",
        "not playwright",
        "-q",
        "-p",
        "no:cacheprovider",
        *args.paths,
    ]
    print(f"Pomiar: {' '.join(cmd)}", file=sys.stderr)
    peaks: dict[int, tuple[str, int]] = {}
    pg_peak = 0
    tree_peak = 0
    stop = threading.Event()

    def sample(root_pid: int):
        nonlocal pg_peak, tree_peak
        root = psutil.Process(root_pid)
        while not stop.is_set():
            total = 0
            try:
                procs = [root, *root.children(recursive=True)]
            except psutil.NoSuchProcess:
                break
            for p in procs:
                try:
                    rss = p.memory_info().rss // MB
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                total += rss
                kind = _classify(p)
                if rss > peaks.get(p.pid, ("", 0))[1]:
                    peaks[p.pid] = (kind, rss)
            tree_peak = max(tree_peak, total)
            pg = _docker_pg_mb(pg_before)
            if pg:
                pg_peak = max(pg_peak, pg)
            stop.wait(2)

    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=REPO)
    t = threading.Thread(target=sample, args=(proc.pid,), daemon=True)
    t.start()
    rc = proc.wait()
    stop.set()
    t.join()
    duration = int(time.monotonic() - started)

    worker_peaks = sorted(
        (rss for kind, rss in peaks.values() if kind == "worker"), reverse=True
    )
    controller = max(
        (rss for kind, rss in peaks.values() if kind == "controller"), default=0
    )
    if not worker_peaks:
        print("Nie znalazlem procesow workerow xdist -- pomiar nieudany.")
        return 1
    profile = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": os.uname().nodename,
        "workers": workers,
        "paths": args.paths,
        "duration_s": duration,
        "pytest_exit_code": rc,
        "worker_peak_mb": worker_peaks[0],
        "worker_peaks_mb": worker_peaks,
        "controller_peak_mb": controller,
        "tree_peak_mb": tree_peak,
        "pg_peak_mb": pg_peak or None,
        "pg_per_worker_mb": (pg_peak // workers) if pg_peak else None,
    }
    PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(profile, indent=2, ensure_ascii=False))
    if rc != 0:
        print(
            f"UWAGA: pytest zakonczyl sie kodem {rc} -- jesli testy padly "
            "wczesnie, szczyty moga byc zanizone.",
            file=sys.stderr,
        )
    print(f"Zapisano {PROFILE.name}. Teraz: make xdist-calc", file=sys.stderr)
    return 0


def _load_profile() -> dict | None:
    if PROFILE.exists():
        return json.loads(PROFILE.read_text())
    return None


def calc() -> tuple[int, dict]:
    prof = _load_profile() or {}
    worker = prof.get("worker_peak_mb") or DEFAULT_WORKER_MB
    controller = prof.get("controller_peak_mb") or DEFAULT_CONTROLLER_MB
    pg = prof.get("pg_per_worker_mb") or DEFAULT_PG_PER_WORKER_MB
    avail = _available_mb()
    reserve = _reserve_mb()
    per_worker = int(worker * _safety()) + pg
    budget = avail - reserve - controller
    n = max(1, min(budget // per_worker, os.cpu_count() or 1))
    info = {
        "profil": PROFILE.name if prof else "brak (wartosci domyslne)",
        "dostepne_mb": avail,
        "rezerwa_mb": reserve,
        "kontroler_mb": controller,
        "worker_szczyt_mb": worker,
        "zapas": _safety(),
        "pg_na_workera_mb": pg,
        "na_workera_mb": per_worker,
        "budzet_mb": budget,
        "cpu": os.cpu_count(),
        "n": n,
    }
    return n, info


def cmd_calc(args) -> int:
    n, info = calc()
    if args.quiet:
        print(n)
        return 0
    print(f"Profil:            {info['profil']}")
    print(f"Dostepna pamiec:   {info['dostepne_mb']} MB")
    print(f"- rezerwa:         {info['rezerwa_mb']} MB (XDIST_RESERVE_MB)")
    print(f"- kontroler:       {info['kontroler_mb']} MB")
    print(f"= budzet:          {info['budzet_mb']} MB")
    print(
        f"Na workera:        {info['worker_szczyt_mb']} MB x {info['zapas']} "
        f"+ PG {info['pg_na_workera_mb']} MB = {info['na_workera_mb']} MB"
    )
    print(f"Bezpieczne -n:     {info['n']}  (CPU: {info['cpu']})")
    if info["profil"].startswith("brak"):
        print("Brak profilu -- zmierz na tej maszynie: make xdist-measure")
    return 0


def cmd_guard(args) -> int:
    limit = max(_available_mb() - _reserve_mb(), 1024)
    print(" ".join(guard_prefix(limit)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="zmierz zuzycie RAM workerow xdist")
    m.add_argument("-n", "--workers", type=int, default=2)
    m.add_argument("paths", nargs="*", default=DEFAULT_SAMPLE_PATHS)
    m.set_defaults(func=cmd_measure)
    c = sub.add_parser("calc", help="policz bezpieczne -n")
    c.add_argument("-q", "--quiet", action="store_true")
    c.set_defaults(func=cmd_calc)
    g = sub.add_parser("guard", help="prefiks systemd-run z limitem pamieci")
    g.set_defaults(func=cmd_guard)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
