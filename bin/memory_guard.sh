#!/usr/bin/env bash
#
# Drukuje prefiks `systemd-run --user --scope ... MemoryMax=...`, pod ktorym
# Makefile puszcza testy (XDIST_GUARD): przekroczenie limitu zabija pytest,
# zamiast wpedzac laptop w swap. Limit = MemAvailable - rezerwa.
# Pusty wynik (bez limitu), gdy to nie Linux albo nie ma user-systemd.
#
# Zmienne: XDIST_RESERVE_MB -- ile MB zostawic dla pulpitu (domyslnie 2048).

set -euo pipefail

[ "$(uname -s)" = Linux ] || exit 0
command -v systemd-run >/dev/null || exit 0
systemd-run --user --scope -q true >/dev/null 2>&1 || exit 0

reserve="${XDIST_RESERVE_MB:-2048}"
avail=$(awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo)
limit=$((avail - reserve))
[ "$limit" -lt 1024 ] && limit=1024

echo "systemd-run --user --scope -q -p MemoryMax=${limit}M -p MemorySwapMax=0"
