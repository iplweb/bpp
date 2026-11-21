#!/usr/bin/env python
"""Benchmark liczby workerow xdist na TEJ maszynie.

Puszcza te sama suite (domyslnie ``-m "not playwright"``) kolejno z kilkoma
wartosciami ``-n``, mierzy czas calego przebiegu (start kontenerow, zbieranie
testow, testy) i zapisuje najlepsza liczbe workerow do
``.pytest-xdist-bench.json`` (gitignored, per maszyna, osobno dla kazdego
``-m``). Hook w ``src/conftest.py`` przycina potem ``-n auto`` do tej wartosci
-- pytest-xdist-memory nadal pilnuje RAM-u, wiec ``-n auto`` = min(RAM, bench).

"Najlepsza" = najmniejsza liczba workerow, ktorej czas miesci sie w
``--tolerance`` (domyslnie 3%) od najszybszego wyniku. Roznice ponizej tego
progu to szum, a mniej workerow to mniej RAM-u i ciepla.

Podczas kazdego przebiegu probkuje pamiec (co 0,5 s): szczyt RSS drzewa
procesow pytest oraz szczyt przyrostu zajetej pamieci systemu (obejmuje tez
kontenery testcontainers). ``--show`` dopasowuje z tego model
``RAM = stala + na_workera * n`` i podaje wymagania: ile RAM-u potrzeba przy
najszybszym ``-n`` oraz ile workerow zmiesci 8/16/32/64/128 GB RAM.

Uzycie (przez make): ``make xdist-bench``, ``make xdist-bench-playwright``.
Recznie::

    uv run python bin/xdist_bench.py --marker "not playwright" \\
        --candidates 12,16,20,24 --repeat 2
    uv run python bin/xdist_bench.py --show
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fixtures.xdist_bench import (  # noqa: E402
    BENCH_FILENAME,
    VERSION,
    empty,
    load,
    rekomendacje,
    suite_key,
)

BENCH_FILE = ROOT / BENCH_FILENAME


def save(data: dict) -> None:
    data["version"] = VERSION
    tmp = BENCH_FILE.with_name(BENCH_FILE.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(BENCH_FILE)


def default_candidates() -> list[int]:
    phys = psutil.cpu_count(logical=False) or 4
    logical = psutil.cpu_count(logical=True) or phys
    raw = {
        phys // 2,
        (3 * phys) // 4,
        phys,
        phys + phys // 4,
        (phys + logical) // 2,
        logical,
    }
    return sorted(n for n in raw if n >= 1)


def memory_cap(marker: str) -> int | None:
    """Ile workerow zmiesci RAM wg pytest-xdist-memory (None = brak pluginu)."""
    try:
        from pytest_xdist_memory import memory, profile
    except ImportError:
        return None
    # Te same wartosci co w pytest.ini / Makefile (default_worker dla
    # Playwrighta podaje Makefile: 1900 MB).
    default_worker = 1900 if "playwright" in marker and "not" not in marker else 700
    est = profile.estimate(
        profile.load(ROOT / ".pytest-xdist-memory.json"),
        suite_key(marker),
        available_mb=memory.available_mb(),
        reserve_mb=2048,
        safety=1.25,
        cpu_cap=10**6,
        default_worker_mb=default_worker,
        default_controller_mb=250,
        extra_per_worker_mb=0,
    )
    return est.workers


def guard_prefix() -> list[str]:
    """Limit pamieci systemd-run (jak XDIST_GUARD w Makefile), Linux only."""
    script = ROOT / "bin" / "memory_guard.sh"
    if os.environ.get("CI") or not script.exists():
        return []
    out = subprocess.run([str(script)], capture_output=True, text=True, check=False)
    return shlex.split(out.stdout.strip())


SUMMARY_RE = re.compile(r"=+ (.*\d+ passed.*) in ([\d.]+)s")


def _zajeta_pamiec_mb() -> float:
    """Pamięć zajęta w systemie (bez cache/buforów) — obejmuje też kontenery
    testcontainers, których nie ma w drzewie procesów pytest."""
    vm = psutil.virtual_memory()
    return (vm.total - vm.available) / 2**20


def _rss_drzewa_mb(proces: psutil.Process) -> float:
    """Suma RSS procesu i wszystkich potomków (kontroler + workery xdist)."""
    suma = 0
    for p in [proces, *proces.children(recursive=True)]:
        try:
            suma += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue  # proces zdążył się zakończyć / cudzy — pomijamy
    return suma / 2**20


class Probkowanie(threading.Thread):
    """Co ``krok_s`` zapisuje szczyt RSS drzewa procesów pytest i szczyt
    przyrostu zajętej pamięci systemu względem stanu sprzed przebiegu."""

    def __init__(self, pid: int, baza_mb: float, krok_s: float = 0.5):
        super().__init__(daemon=True)
        self.proces = psutil.Process(pid)
        self.baza_mb = baza_mb
        self.krok_s = krok_s
        self.szczyt_rss_mb = 0.0
        self.szczyt_ram_mb = 0.0
        self.stop = threading.Event()

    def run(self):
        while not self.stop.wait(self.krok_s):
            try:
                rss = _rss_drzewa_mb(self.proces)
            except psutil.NoSuchProcess:
                break  # pytest się zakończył
            self.szczyt_rss_mb = max(self.szczyt_rss_mb, rss)
            self.szczyt_ram_mb = max(
                self.szczyt_ram_mb, _zajeta_pamiec_mb() - self.baza_mb
            )


def run_once(n: int, marker: str, extra: list[str], log: Path) -> dict:
    cmd = [
        *guard_prefix(),
        "uv",
        "run",
        "pytest",
        "-n",
        str(n),
        "-m",
        marker,
        "--xdist-memory",
        "-p",
        "no:cacheprovider",
        *extra,
    ]
    baza_mb = statistics.median(_zajeta_pamiec_mb() for _ in range(3))
    start = time.monotonic()
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        probki = Probkowanie(proc.pid, baza_mb)
        probki.start()
        rc = proc.wait()
        probki.stop.set()
        probki.join()
    wall = time.monotonic() - start
    text = log.read_text(errors="replace")
    matches = list(SUMMARY_RE.finditer(text))
    match = matches[-1] if matches else None
    return {
        "n": n,
        "rc": rc,
        "wall_s": round(wall, 2),
        "pytest_s": float(match.group(2)) if match else None,
        "summary": match.group(1) if match else None,
        "peak_rss_mb": round(probki.szczyt_rss_mb),
        "peak_ram_mb": round(probki.szczyt_ram_mb),
    }


def pick_best(results: dict[int, list[dict]], tolerance: float) -> int | None:
    medians = {
        n: statistics.median(r["wall_s"] for r in runs)
        for n, runs in results.items()
        if runs and all(r["rc"] == 0 for r in runs)
    }
    if not medians:
        return None
    fastest = min(medians.values())
    return min(n for n, t in medians.items() if t <= fastest * (1 + tolerance))


def show(data: dict) -> None:
    fp = data["fingerprint"]
    ram_gb = psutil.virtual_memory().total / 2**30
    print(
        f"{fp['hostname']}: {fp['cpu_model']} "
        f"({fp['physical_cpus']} rdzeni / {fp['logical_cpus']} watkow, "
        f"{ram_gb:.0f} GB RAM)"
    )
    if not data["suites"]:
        print("  brak pomiarow -- odpal `make xdist-bench`")
    for key, suite in data["suites"].items():
        print(f"  -m {key!r}: best -n {suite['best']} ({suite['measured_at']})")
        for row in suite["table"]:
            mark = " <-- best" if row["n"] == suite["best"] else ""
            status = "" if row["ok"] else "  (FAILED -- pominiete)"
            pamiec = ""
            if row.get("peak_ram_mb") is not None:
                pamiec = (
                    f"  szczyt RAM {row['peak_ram_mb'] / 1024:5.1f} GB"
                    f" (pytest {row['peak_rss_mb'] / 1024:.1f} GB)"
                )
            print(
                f"    -n {row['n']:>3}: {row['median_wall_s']:7.1f} s"
                f"{pamiec}{mark}{status}"
            )
        print("  Wymagania:")
        for linia in rekomendacje(suite, fp):
            print(linia)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--marker", default="not playwright", help="wyrazenie -m")
    parser.add_argument(
        "--candidates",
        help="lista -n po przecinku (domyslnie z liczby rdzeni, np. 8,12,16,20,24,32)",
    )
    parser.add_argument("--repeat", type=int, default=1, help="przebiegi na -n")
    parser.add_argument("--tolerance", type=float, default=0.03)
    parser.add_argument("--show", action="store_true", help="tylko pokaz zapisane")
    parser.add_argument(
        "pytest_args", nargs="*", help="dodatkowe argumenty pytest (po --)"
    )
    args = parser.parse_args()

    data, problem = load(BENCH_FILE)
    if problem:
        print(f"xdist-bench: {BENCH_FILENAME} {problem} -- zaczynam od zera")
        data = empty()
    if args.show:
        show(data)
        return 0

    candidates = (
        sorted({int(x) for x in args.candidates.split(",")})
        if args.candidates
        else default_candidates()
    )
    cap = memory_cap(args.marker)
    if cap is not None and any(n > cap for n in candidates):
        skipped = [n for n in candidates if n > cap]
        candidates = [n for n in candidates if n <= cap] or [cap]
        print(f"xdist-bench: RAM miesci {cap} workerow -- pomijam -n {skipped}")

    log_dir = ROOT / ".pytest-xdist-bench-logs"
    log_dir.mkdir(exist_ok=True)
    print(
        f"xdist-bench: -m {args.marker!r}, -n {candidates}, x{args.repeat}; "
        f"logi w {log_dir.relative_to(ROOT)}/"
    )

    results: dict[int, list[dict]] = {n: [] for n in candidates}
    # Przeplatamy kolejnosc (16,20,24,16,20,24...), zeby dryf temperatury /
    # tla nie faworyzowal jednej wartosci.
    for rep in range(args.repeat):
        for n in candidates:
            log = log_dir / f"n{n}-r{rep}.log"
            res = run_once(n, args.marker, args.pytest_args, log)
            results[n].append(res)
            pyt = f"{res['pytest_s']:.1f} s" if res["pytest_s"] else "?"
            status = "ok" if res["rc"] == 0 else f"rc={res['rc']} ({log.name})"
            print(
                f"  -n {n:>3}: {res['wall_s']:6.1f} s calosc, pytest {pyt}  {status}",
                flush=True,
            )

    best = pick_best(results, args.tolerance)
    if best is None:
        print("xdist-bench: zaden przebieg nie przeszedl -- nic nie zapisuje")
        return 1

    table = [
        {
            "n": n,
            "ok": all(r["rc"] == 0 for r in runs),
            "median_wall_s": round(statistics.median(r["wall_s"] for r in runs), 2),
            # szczyt z powtórzeń — do wymiarowania liczy się najgorszy przypadek
            "peak_ram_mb": max(r["peak_ram_mb"] for r in runs),
            "peak_rss_mb": max(r["peak_rss_mb"] for r in runs),
            "runs": runs,
        }
        for n, runs in results.items()
    ]
    data["suites"][suite_key(args.marker)] = {
        "best": best,
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tolerance": args.tolerance,
        "pytest_args": args.pytest_args,
        "table": table,
    }
    save(data)
    print(f"xdist-bench: zapisano do {BENCH_FILE.name}")
    show(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
