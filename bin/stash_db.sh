#!/bin/bash
# Stash the 'bpp' database to bpp_[skrot]_[timestamp]
# Automatically queries bpp_uczelnia.skrot and bpp_rekord_mat.ostatnio_zmieniony
#
# Usage: stash_db.sh
#
# Example: stash_db.sh
#   Queries database and renames: bpp -> bpp_ABC_20251020143022
#
# Environment variables used:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD
#   (Standard PostgreSQL environment variables)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo "Usage: $0"
    echo ""
    echo "Stashes the 'bpp' database to bpp_<skrot>_<timestamp>"
    echo "Automatically queries bpp_uczelnia.skrot and bpp_rekord_mat.ostatnio_zmieniony"
    echo ""
    echo "Example:"
    echo "  $0"
    echo "  Queries: SELECT skrot FROM bpp_uczelnia, MAX(ostatnio_zmieniony) FROM bpp_rekord_mat"
    echo "  Result: bpp -> bpp_ABC_20251020143022"
    echo ""
    echo "Environment variables:"
    echo "  PGHOST, PGPORT, PGUSER, PGPASSWORD - PostgreSQL connection parameters"
    exit 1
}

# Check for help flag
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# Check for unexpected parameters
if [ $# -ne 0 ]; then
    echo -e "${RED}Error: This script does not take parameters${NC}" >&2
    usage
fi

SOURCE_DB="bpp"

# Check if source database exists
if ! psql -lqt | cut -d \| -f 1 | grep -qw "$SOURCE_DB"; then
    echo -e "${RED}Error: Database '${SOURCE_DB}' does not exist${NC}" >&2
    exit 1
fi

# Query the database for skrot and ostatnio_zmieniony
echo -e "${YELLOW}Querying database for stash parameters...${NC}"
QUERY_RESULT=$(psql -d "$SOURCE_DB" -A -t -F'|' -c "SELECT (SELECT skrot FROM bpp_uczelnia LIMIT 1), COALESCE(to_char(MAX(ostatnio_zmieniony), 'YYYYMMDDHH24MISS'), to_char(NOW(), 'YYYYMMDDHH24MISS')) FROM bpp_rekord_mat;")

# Parse the result using | as separator
SKROT=$(echo "$QUERY_RESULT" | cut -d '|' -f 1 | xargs)
TIMESTAMP=$(echo "$QUERY_RESULT" | cut -d '|' -f 2 | xargs)

# Validate we got values
if [ -z "$SKROT" ] || [ -z "$TIMESTAMP" ]; then
    echo -e "${RED}Error: Could not query skrot from bpp_uczelnia or ostatnio_zmieniony from bpp_rekord_mat${NC}" >&2
    exit 1
fi

TARGET_DB="bpp_${SKROT}_${TIMESTAMP}"

echo "  Skrot: ${SKROT}"
echo "  Timestamp: ${TIMESTAMP}"
echo ""

echo -e "${YELLOW}Stashing database...${NC}"
echo "  Source: ${SOURCE_DB}"
echo "  Target: ${TARGET_DB}"
echo ""

# Check if target database already exists
if psql -lqt | cut -d \| -f 1 | grep -qw "$TARGET_DB"; then
    echo -e "${RED}Error: Database '${TARGET_DB}' already exists${NC}" >&2
    exit 1
fi

# Terminate existing connections to the source database
echo "Terminating existing connections to ${SOURCE_DB}..."
psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${SOURCE_DB}' AND pid <> pg_backend_pid();" > /dev/null

# Rename the database
echo "Renaming database..."
psql -d postgres -c "ALTER DATABASE \"${SOURCE_DB}\" RENAME TO \"${TARGET_DB}\";"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Success!${NC} Database renamed: ${SOURCE_DB} -> ${TARGET_DB}"
else
    echo -e "${RED}Error: Failed to rename database${NC}" >&2
    exit 1
fi
