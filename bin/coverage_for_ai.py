#!/usr/bin/env python3
"""LLM-friendly coverage gap reporter.

Reads ``coverage.json`` (produced by ``coverage json``) and emits a compact,
deterministically-sorted ranking of files with the lowest coverage. Designed
to be piped into an AI assistant context: the agent can read the ranking,
pick the worst offenders, then ``Read`` those files at the indicated line
ranges to write missing tests.

Output format (one record per line, prefixed with a self-describing header)::

    src/bpp/views/foo.py COVER=12.5% STMTS=80 MISS=70 BRANCH=5 MISSING=5-12,18-25,30-45

Why text and not JSON? Roughly 3× lower token cost for the same information,
still trivially parseable, and the inline header documents the schema.

Usage::

    python bin/coverage_for_ai.py [--threshold 90] [--limit 30] \\
        [--input coverage.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Heuristic skip rules layered on top of [tool.coverage.run].omit.
# coverage.py's omit is authoritative; this is defense in depth for cases
# where the report is generated without the project config (e.g. CI artefact
# inspected on a developer machine from a different repo root).
SKIP_SUBSTRINGS = (
    "/migrations/",
    "/tests/",
    "/test_",
    "/__pycache__/",
    "/site-packages/",
    "/staticroot/",
)
# Tiny __init__.py files dominate the bottom of the ranking without being
# actionable; drop them below this statement count.
TRIVIAL_INIT_MAX_STMTS = 5


def compact_ranges(line_numbers: list[int]) -> str:
    """Turn ``[1,2,3,5,6,9]`` into ``"1-3,5-6,9"``."""
    if not line_numbers:
        return ""
    nums = sorted(set(line_numbers))
    out: list[str] = []
    start = end = nums[0]
    for n in nums[1:]:
        if n == end + 1:
            end = n
        else:
            out.append(f"{start}-{end}" if start != end else str(start))
            start = end = n
    out.append(f"{start}-{end}" if start != end else str(start))
    return ",".join(out)


def should_skip(path: str, num_statements: int) -> bool:
    if any(needle in path for needle in SKIP_SUBSTRINGS):
        return True
    if Path(path).name == "__init__.py" and num_statements < TRIVIAL_INIT_MAX_STMTS:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("coverage.json"),
        help="Path to coverage.json (default: ./coverage.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=90.0,
        help="Only report files with coverage strictly below this %% (default: 90.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of files to print (default: 30)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        sys.stderr.write(
            f"error: {args.input} not found. Run `make coverage-ai` first.\n"
        )
        return 2

    data = json.loads(args.input.read_text())
    files: dict[str, dict] = data.get("files", {})

    candidates: list[tuple[float, int, str, dict]] = []
    skipped_trivial = 0
    for path, fd in files.items():
        summary = fd.get("summary", {})
        n_stmts = summary.get("num_statements", 0)
        if should_skip(path, n_stmts):
            skipped_trivial += 1
            continue
        if n_stmts == 0:
            skipped_trivial += 1
            continue
        pct = summary.get("percent_covered", 100.0)
        if pct >= args.threshold:
            continue
        candidates.append((pct, -n_stmts, path, fd))

    # Sort: lowest coverage first; among ties, largest file first (more
    # statements = more leverage from a single new test file).
    candidates.sort()

    total_files = len(files)
    eligible = total_files - skipped_trivial
    shown = min(len(candidates), args.limit)

    print(
        f"# Coverage gaps below {args.threshold:.1f}% — "
        f"showing {shown} of {len(candidates)} below threshold "
        f"({eligible} eligible source files, {skipped_trivial} skipped as "
        f"migrations/tests/trivial)"
    )
    print(
        "# Schema: <path> COVER=<%> STMTS=<n> MISS=<n> BRANCH=<n-partial> "
        "MISSING=<line-ranges>"
    )
    print(
        "# Sorted: ascending coverage; ties broken by descending statement "
        "count (bigger files first)."
    )
    print()

    for pct, _neg_stmts, path, fd in candidates[: args.limit]:
        summary = fd["summary"]
        missing_lines = fd.get("missing_lines", [])
        ranges = compact_ranges(missing_lines)
        # missing_branches is partial-branch count; coverage.json names it
        # missing_branches in summary on coverage>=7.
        n_partial = summary.get("missing_branches", 0)
        print(
            f"{path} "
            f"COVER={pct:.1f}% "
            f"STMTS={summary['num_statements']} "
            f"MISS={summary['missing_lines']} "
            f"BRANCH={n_partial} "
            f"MISSING={ranges or '-'}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
