#!/bin/sh -euo pipefail

echo "Most recent migration for ``bpp_refresh_cache`` PL/Python function"
./bin/find-latest-migration-with-text.sh "CREATE OR REPLACE FUNCTION bpp_refresh_cache"
echo ""
echo "Most recent migration for ``bpp_rekord_mat``"
./bin/find-latest-migration-with-text.sh "CREATE TABLE bpp_rekord_mat"
