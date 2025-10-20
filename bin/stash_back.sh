#!/bin/bash
# Restore the most recent bpp_[skrot]_* database back to 'bpp'
# Finds the most recent by parsing timestamp from database name
#
# Usage: stash_back.sh <skrot>
#   skrot: The uczelnia.skrot value (institution abbreviation)
#
# Example: stash_back.sh ABC
#   Finds most recent: bpp_ABC_20251020143022 (sorted by timestamp)
#   Result: bpp_ABC_20251020143022 -> bpp
#   If bpp exists, it will be renamed to bpp_old_[YYYYMMDDHH24MISS] first
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
    echo "Usage: $0 <skrot>"
    echo ""
    echo "Restores the most recent bpp_<skrot>_* database to 'bpp'"
    echo "Selects the most recent by sorting database names by timestamp"
    echo "If 'bpp' exists, it will be renamed to bpp_old_<timestamp> first"
    echo ""
    echo "Arguments:"
    echo "  skrot    The uczelnia.skrot value (institution abbreviation)"
    echo ""
    echo "Example:"
    echo "  $0 ABC"
    echo "  Finds: bpp_ABC_20251020143022 (most recent by timestamp)"
    echo "  Result: bpp_ABC_20251020143022 -> bpp"
    echo ""
    echo "Environment variables:"
    echo "  PGHOST, PGPORT, PGUSER, PGPASSWORD - PostgreSQL connection parameters"
    exit 1
}

# Check for required parameter
if [ $# -ne 1 ]; then
    echo -e "${RED}Error: Missing required parameter${NC}" >&2
    usage
fi

SKROT="$1"
CURRENT_TIMESTAMP=$(date +%Y%m%d%H%M%S)
TARGET_DB="bpp"

# Validate skrot (alphanumeric and underscore only)
if ! [[ "$SKROT" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo -e "${RED}Error: Skrot must contain only alphanumeric characters and underscores${NC}" >&2
    exit 1
fi

# Find the most recent database matching the pattern (sorted by timestamp in name)
PATTERN="bpp_${SKROT}_%"
SOURCE_DB=$(psql -d postgres -t -c "SELECT datname FROM pg_database WHERE datname LIKE '${PATTERN}' ORDER BY datname DESC LIMIT 1;" | xargs)

# Check if a matching database was found
if [ -z "$SOURCE_DB" ]; then
    echo -e "${RED}Error: No database found matching pattern '${PATTERN}'${NC}" >&2
    echo ""
    echo "Use 'stash_list.sh ${SKROT}' to see available databases"
    exit 1
fi

echo -e "${YELLOW}Restoring database...${NC}"
echo "  Source: ${SOURCE_DB}"
echo "  Target: ${TARGET_DB}"
echo ""

# Check if target database exists
if psql -lqt | cut -d \| -f 1 | grep -qw "$TARGET_DB"; then
    BACKUP_DB="bpp_old_${CURRENT_TIMESTAMP}"
    echo -e "${YELLOW}Database '${TARGET_DB}' exists. Renaming to '${BACKUP_DB}' first...${NC}"

    # Check if backup database name already exists
    COUNTER=1
    ORIGINAL_BACKUP_DB="${BACKUP_DB}"
    while psql -lqt | cut -d \| -f 1 | grep -qw "$BACKUP_DB"; do
        BACKUP_DB="${ORIGINAL_BACKUP_DB}_${COUNTER}"
        COUNTER=$((COUNTER + 1))
    done

    # Terminate existing connections to the target database
    echo "Terminating existing connections to ${TARGET_DB}..."
    psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();" > /dev/null

    # Rename existing bpp database
    psql -d postgres -c "ALTER DATABASE ${TARGET_DB} RENAME TO ${BACKUP_DB};"
    echo -e "${GREEN}Existing database saved as: ${BACKUP_DB}${NC}"
    echo ""
fi

# Terminate existing connections to the source database
echo "Terminating existing connections to ${SOURCE_DB}..."
psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${SOURCE_DB}' AND pid <> pg_backend_pid();" > /dev/null

# Rename the source database to bpp
echo "Restoring database..."
psql -d postgres -c "ALTER DATABASE ${SOURCE_DB} RENAME TO ${TARGET_DB};"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Success!${NC} Database restored: ${SOURCE_DB} -> ${TARGET_DB}"
else
    echo -e "${RED}Error: Failed to restore database${NC}" >&2
    exit 1
fi
