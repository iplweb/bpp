#!/usr/bin/env python
"""Ile workerow xdist zmiesci sie w RAM-ie tej maszyny.

Na maszynie interaktywnej (laptop z pulpitem) waskim gardlem testow jest
pamiec, nie CPU: `pytest -n auto` na 14 rdzeniach / 14 GB RAM wpedzil
system w thrashing swapu i wymagal twardego resetu. Workery xdist ROSNA
w trakcie przebiegu, jesli GC nie sprzata cykli referencji (zmierzone bez
okresowego ``gc.collect()``: 400 MB -> 1,75 GB w 3 minuty; z nim, patrz
pytest-gc-steward w pytest.ini: ~450-650 MB). Kazdy worker
doklada tez backend PostgreSQL w testcontainerze.

Workery suity Playwright sa duzo ciezsze: kazdy ciagnie za soba wlasne
Chromium (kilka procesow) i podproces Daphne (`channels_live_server`).
Dlatego pamiec workera liczymy razem z CALYM jego poddrzewem procesow,
a Playwright ma osobny profil (`--suite playwright`).

Podkomendy:

    measure  -- puszcza probke testow z `-n 2`, probkuje pamiec drzewa
                procesow pytest i PG w kontenerze, zapisuje profil do
                `.xdist-mem-profile.json` (`--suite playwright`:
                `.xdist-mem-profile-playwright.json`; gitignored, per
                maszyna).
    calc     -- z profilu + aktualnie dostepnej pamieci liczy bezpieczne
                `-n`. `--quiet` drukuje sama liczbe (dla Makefile).
                Dla `--suite playwright` na Apple Silicon gorny limit to
                liczba rdzeni wydajnosciowych (E-cores nie uciagaja
                Chromium + Daphne).
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

# Suita Playwright: worker + Chromium + Daphne. Wartosci domyslne (gdy na
# maszynie nie ma jeszcze profilu) z pomiaru 2026-11-06 na thinkpad14s
# (150 testow, -n 2, PSS): worker 1380 MB, PG 465 MB/worker.
SUITES = {
    "default": {
        "profile": REPO / ".xdist-mem-profile.json",
        "marker": "not playwright",
        "paths": DEFAULT_SAMPLE_PATHS,
        "worker_mb": DEFAULT_WORKER_MB,
        "controller_mb": DEFAULT_CONTROLLER_MB,
        "pg_per_worker_mb": DEFAULT_PG_PER_WORKER_MB,
        "make_measure": "make xdist-measure",
    },
    "playwright": {
        "profile": REPO / ".xdist-mem-profile-playwright.json",
        "marker": "playwright",
        # `src/fixtures` musi byc na liscie: marker `playwright` dokleja
        # hook z src/fixtures/conftest.py, ladowany tylko gdy ten katalog
        # jest zbierany -- bez niego `-m playwright` lapie kilka testow.
        "paths": [
            "src/fixtures",
            "src/bpp/tests/test_playwright/test_admin",
            "src/integration_tests",
        ],
        "worker_mb": 1380,
        "controller_mb": DEFAULT_CONTROLLER_MB,
        "pg_per_worker_mb": 465,
        "make_measure": "make xdist-measure-playwright",
    },
}


def _reserve_mb() -> int:
    return int(os.environ.get("XDIST_RESERVE_MB", "2048"))


def _safety() -> float:
    return float(os.environ.get("XDIST_SAFETY", "1.25"))


def _available_mb() -> int:
    return psutil.virtual_memory().available // MB


def _mem_mb(proc: psutil.Process) -> int:
    """PSS na Linuksie (sprawiedliwy udzial w pamieci wspoldzielonej --
    procesy Chromium dziela miedzy soba sporo stron, wiec suma RSS
    zawyzalaby wynik kilkukrotnie), RSS gdzie indziej."""
    if sys.platform.startswith("linux"):
        try:
            return proc.memory_full_info().pss // MB
        except psutil.AccessDenied:
            pass  # brak dostepu do smaps -- spadamy do RSS ponizej
    return proc.memory_info().rss // MB


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


def _snapshot(root: psutil.Process) -> tuple[int, int, dict[int, int]] | None:
    """Jedna probka: (suma drzewa, kontroler, {pid workera: poddrzewo}).

    Pamiec workera to suma jego i WSZYSTKICH potomkow (dla Playwrighta:
    Chromium + Daphne). None, gdy proces glowny juz nie zyje."""
    try:
        procs = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return None
    mem: dict[int, int] = {}
    for p in procs:
        try:
            mem[p.pid] = _mem_mb(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    controller = 0
    per_worker: dict[int, int] = {}
    for p in procs:
        kind = _classify(p)
        if kind == "controller":
            controller = max(controller, mem.get(p.pid, 0))
        elif kind == "worker":
            try:
                sub = p.children(recursive=True)
            except psutil.NoSuchProcess:
                continue
            per_worker[p.pid] = mem.get(p.pid, 0) + sum(mem.get(c.pid, 0) for c in sub)
    return sum(mem.values()), controller, per_worker


def cmd_measure(args) -> int:
    suite = SUITES[args.suite]
    workers = args.workers
    paths = args.paths or suite["paths"]
    pg_before = _docker_pg_names()
    limit = max(_available_mb() - _reserve_mb(), 1024)
    cmd = guard_prefix(limit) + [
        "uv",
        "run",
        "pytest",
        "-n",
        str(workers),
        "-m",
        suite["marker"],
        "-q",
        "-p",
        "no:cacheprovider",
        *paths,
    ]
    print(f"Pomiar: {' '.join(cmd)}", file=sys.stderr)
    # Szczyt per worker = szczyt sumy pamieci CALEGO poddrzewa workera
    # (dla Playwrighta: Chromium + Daphne), mierzonej w jednej probce.
    worker_peaks: dict[int, int] = {}
    controller = 0
    pg_peak = 0
    tree_peak = 0
    stop = threading.Event()

    def sample(root_pid: int):
        nonlocal pg_peak, tree_peak, controller
        root = psutil.Process(root_pid)
        while not stop.is_set():
            snap = _snapshot(root)
            if snap is None:
                break
            total, ctrl, per_worker = snap
            tree_peak = max(tree_peak, total)
            controller = max(controller, ctrl)
            for pid, mb in per_worker.items():
                worker_peaks[pid] = max(worker_peaks.get(pid, 0), mb)
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

    peaks = sorted(worker_peaks.values(), reverse=True)
    if not peaks:
        print("Nie znalazlem procesow workerow xdist -- pomiar nieudany.")
        return 1
    profile = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": os.uname().nodename,
        "suite": args.suite,
        "metric": "pss" if sys.platform.startswith("linux") else "rss",
        "workers": workers,
        "paths": paths,
        "duration_s": duration,
        "pytest_exit_code": rc,
        "worker_peak_mb": peaks[0],
        "worker_peaks_mb": peaks,
        "controller_peak_mb": controller,
        "tree_peak_mb": tree_peak,
        "pg_peak_mb": pg_peak or None,
        "pg_per_worker_mb": (pg_peak // workers) if pg_peak else None,
    }
    path = suite["profile"]
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(profile, indent=2, ensure_ascii=False))
    if rc != 0:
        print(
            f"UWAGA: pytest zakonczyl sie kodem {rc} -- jesli testy padly "
            "wczesnie, szczyty moga byc zanizone.",
            file=sys.stderr,
        )
    print(f"Zapisano {path.name}.", file=sys.stderr)
    return 0


def _load_profile(suite: str) -> dict | None:
    path = SUITES[suite]["profile"]
    if path.exists():
        return json.loads(path.read_text())
    return None


def _cpu_cap(suite: str) -> int:
    """Gorny limit workerow z CPU. Dla Playwrighta na Apple Silicon:
    tylko rdzenie wydajnosciowe (zmierzone na 12P+4E: -n 16 nie jest
    szybsze od -n 12, E-cores dokladaja tylko rywalizacje)."""
    cpus = os.cpu_count() or 1
    if suite == "playwright" and sys.platform == "darwin":
        out = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if out.isdigit():
            return int(out)
    return cpus


def calc(suite: str = "default") -> tuple[int, dict]:
    conf = SUITES[suite]
    prof = _load_profile(suite) or {}
    worker = prof.get("worker_peak_mb") or conf["worker_mb"]
    controller = prof.get("controller_peak_mb") or conf["controller_mb"]
    pg = prof.get("pg_per_worker_mb") or conf["pg_per_worker_mb"]
    avail = _available_mb()
    reserve = _reserve_mb()
    per_worker = int(worker * _safety()) + pg
    budget = avail - reserve - controller
    cpu = _cpu_cap(suite)
    n = max(1, min(budget // per_worker, cpu))
    info = {
        "suite": suite,
        "profil": conf["profile"].name if prof else "brak (wartosci domyslne)",
        "make_measure": conf["make_measure"],
        "dostepne_mb": avail,
        "rezerwa_mb": reserve,
        "kontroler_mb": controller,
        "worker_szczyt_mb": worker,
        "zapas": _safety(),
        "pg_na_workera_mb": pg,
        "na_workera_mb": per_worker,
        "budzet_mb": budget,
        "cpu": cpu,
        "n": n,
    }
    return n, info


def cmd_calc(args) -> int:
    n, info = calc(args.suite)
    if args.quiet:
        print(n)
        return 0
    print(f"Suita:             {info['suite']}")
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
        print(f"Brak profilu -- zmierz na tej maszynie: {info['make_measure']}")
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
    m.add_argument("--suite", choices=SUITES, default="default")
    m.add_argument("paths", nargs="*", help="domyslnie: probka wlasciwa dla suity")
    m.set_defaults(func=cmd_measure)
    c = sub.add_parser("calc", help="policz bezpieczne -n")
    c.add_argument("-q", "--quiet", action="store_true")
    c.add_argument("--suite", choices=SUITES, default="default")
    c.set_defaults(func=cmd_calc)
    g = sub.add_parser("guard", help="prefiks systemd-run z limitem pamieci")
    g.set_defaults(func=cmd_guard)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
