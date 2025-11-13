#!/bin/bash
set -euo pipefail

# Check if PostgreSQL is running on port 5432
if nc -z localhost 5432 2>/dev/null; then
    echo -n "Obecnie zainstalowana baza to: "
    psql --csv -c "select nazwa from bpp_uczelnia" bpp | tail -1
fi
