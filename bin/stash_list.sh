#!/bin/bash
# List databases matching the bpp_* pattern
#
# Usage: stash_list.sh [label]
#   label: Optional filter to show only databases with this label
#
# Examples:
#   stash_list.sh           # Lists all bpp_* databases
#   stash_list.sh backup    # Lists only bpp_backup_* databases
#
# Environment variables used:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD
#   (Standard PostgreSQL environment variables)

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo "Usage: $0 [label]"
    echo ""
    echo "Lists databases matching the bpp_* pattern"
    echo ""
    echo "Arguments:"
    echo "  label    Optional. Filter to show only bpp_<label>_* databases"
    echo ""
    echo "Examples:"
    echo "  $0           # Lists all bpp_* databases"
    echo "  $0 backup    # Lists only bpp_backup_* databases"
    echo ""
    echo "Environment variables:"
    echo "  PGHOST, PGPORT, PGUSER, PGPASSWORD - PostgreSQL connection parameters"
    exit 1
}

# Check for help flag
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# Determine the pattern to search for
if [ $# -eq 0 ]; then
    PATTERN="bpp_%"
    LABEL_TEXT="all stashed databases"
elif [ $# -eq 1 ]; then
    LABEL="$1"
    # Validate label (alphanumeric and underscore only)
    if ! [[ "$LABEL" =~ ^[a-zA-Z0-9_]+$ ]]; then
        echo -e "${RED}Error: Label must contain only alphanumeric characters and underscores${NC}" >&2
        exit 1
    fi
    PATTERN="bpp_${LABEL}_%"
    LABEL_TEXT="databases with label '${LABEL}'"
else
    echo "Error: Too many arguments" >&2
    usage
fi

echo -e "${CYAN}Listing ${LABEL_TEXT}...${NC}"
echo ""

# Query for databases matching the pattern
DATABASES=$(psql -d postgres -t -c "SELECT datname FROM pg_database WHERE datname LIKE '${PATTERN}' ORDER BY datname;")

# Check if any databases were found
if [ -z "$DATABASES" ]; then
    echo "No databases found matching pattern: ${PATTERN}"
    exit 0
fi

# Display the results
COUNT=0
while IFS= read -r db; do
    # Trim whitespace
    db=$(echo "$db" | xargs)
    if [ -n "$db" ]; then
        echo -e "${GREEN}  ${db}${NC}"
        COUNT=$((COUNT + 1))
    fi
done <<< "$DATABASES"

echo ""
echo -e "${YELLOW}Total: ${COUNT} database(s)${NC}"
