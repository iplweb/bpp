#!/bin/bash

# Script to find the most recent SQL migration file containing a given string
# Usage: ./find-latest-migration-with-text.sh "search_string"
# Example: ./find-latest-migration-with-text.sh "CREATE OR REPLACE FUNCTION bpp_refresh_cache"

if [ $# -eq 0 ]; then
    echo "Usage: $0 \"search_string\""
    echo "Example: $0 \"CREATE OR REPLACE FUNCTION bpp_refresh_cache\""
    exit 1
fi

SEARCH_STRING="$1"
MIGRATIONS_DIR="src/bpp/migrations"

# Check if migrations directory exists
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "Error: Migrations directory '$MIGRATIONS_DIR' not found"
    exit 1
fi

# Find all .sql files that contain the search string, extract the leading number,
# sort by number (descending), and return the first (highest numbered) file
LATEST_FILE=$(grep -l "$SEARCH_STRING" "$MIGRATIONS_DIR"/*.sql 2>/dev/null | \
    sed 's/.*\/\([0-9]\{4\}\)_.*/\1 &/' | \
    sort -nr | \
    head -1 | \
    cut -d' ' -f2-)

if [ -n "$LATEST_FILE" ]; then
    echo "$LATEST_FILE"
else
    echo "No SQL migration file found containing: '$SEARCH_STRING'"
    exit 1
fi
