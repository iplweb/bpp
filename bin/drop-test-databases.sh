#!/bin/sh
# Kasuje wszystkie testowe bazy danych (test_bpp, test_bpp_gw*, etc.)
set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"

"$SCRIPT_DIR/drop-databases-like.sh" -f -y test_bpp
