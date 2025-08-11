#!/bin/bash
set -euo pipefail

echo -n "Obecnie zainstalowana baza to: "
psql --csv -c "select nazwa from bpp_uczelnia" bpp | tail -1
