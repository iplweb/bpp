#!/bin/bash
# Displays current port configuration with URLs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# Source .env if exists
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

# Get worktree index from git
WORKTREE_COUNT=$(git worktree list 2>/dev/null | wc -l | tr -d ' ')
WORKTREE_INDEX=$((WORKTREE_COUNT - 1))

# Use defaults if variables not set
DB_PORT="${DJANGO_BPP_DB_PORT:-5432}"
APP_PORT="${DJANGO_BPP_PORT_APP:-8000}"
HTTP_PORT="${DJANGO_BPP_PORT_HTTP:-1080}"
HTTPS_PORT="${DJANGO_BPP_PORT_HTTPS:-10443}"
REDIS_PORT="${DJANGO_BPP_REDIS_PORT:-6379}"
RABBITMQ_PORT="${DJANGO_BPP_RABBITMQ_PORT:-5672}"
RABBITMQ_MGMT_PORT="${DJANGO_BPP_PORT_RABBITMQ_MGMT:-15672}"

# Unicode checkmarks with colors (using $'...' syntax for proper escape)
GREEN=$'\033[32m'
RED=$'\033[31m'
NC=$'\033[0m'

# Function to print port line with status
print_port_line() {
    local port=$1
    local name=$2
    local url=$3

    if nc -z localhost "$port" 2>/dev/null; then
        local status="${GREEN}✓${NC}"
    else
        local status="${RED}✗${NC}"
    fi

    if [[ -n "$url" ]]; then
        printf "  %b %-14s port %-5s -> %s\n" "$status" "$name" "$port" "$url"
    else
        printf "  %b %-14s port %-5s\n" "$status" "$name" "$port"
    fi
}

echo ""
echo "=== BPP Docker Port Configuration (worktree index: $WORKTREE_INDEX) ==="
echo ""
print_port_line "$DB_PORT" "PostgreSQL:" ""
print_port_line "$APP_PORT" "Django App:" "http://127.0.0.1:$APP_PORT"
print_port_line "$HTTP_PORT" "HTTP:" "http://127.0.0.1:$HTTP_PORT"
print_port_line "$HTTPS_PORT" "HTTPS:" "https://127.0.0.1:$HTTPS_PORT"
print_port_line "$REDIS_PORT" "Redis:" ""
print_port_line "$RABBITMQ_PORT" "RabbitMQ:" ""
print_port_line "$RABBITMQ_MGMT_PORT" "RabbitMQ UI:" "http://127.0.0.1:$RABBITMQ_MGMT_PORT"
echo ""

# Docker Compose container status
if command -v docker &> /dev/null; then
    cd "$PROJECT_DIR" || exit

    # Get all containers with their status and health
    ALL_CONTAINERS=$(docker compose ps -a --format "{{.Name}}|{{.Status}}|{{.Health}}" 2>/dev/null)

    if [[ -n "$ALL_CONTAINERS" ]]; then
        # Parse containers by status/health
        HEALTHY=""
        UNHEALTHY=""
        RUNNING_NO_HEALTH=""
        STOPPED=""
        OTHER=""

        while IFS='|' read -r name status health; do
            if [[ "$status" == *"Up"* ]]; then
                if [[ "$health" == "healthy" ]]; then
                    HEALTHY="${HEALTHY}${name}\n"
                elif [[ "$health" == "unhealthy" ]]; then
                    UNHEALTHY="${UNHEALTHY}${name}\n"
                else
                    RUNNING_NO_HEALTH="${RUNNING_NO_HEALTH}${name}\n"
                fi
            elif [[ "$status" == *"Exited"* ]]; then
                STOPPED="${STOPPED}${name}\n"
            else
                OTHER="${OTHER}${name} (${status})\n"
            fi
        done <<< "$ALL_CONTAINERS"

        echo "=== Docker Compose Container Status ==="
        echo ""

        if [[ -n "$HEALTHY" ]]; then
            echo "  Healthy (running):"
            echo -e "$HEALTHY" | sort | while read -r name; do
                [[ -n "$name" ]] && printf "    [OK] %s\n" "$name"
            done
            echo ""
        fi

        if [[ -n "$RUNNING_NO_HEALTH" ]]; then
            echo "  Running (no healthcheck):"
            echo -e "$RUNNING_NO_HEALTH" | sort | while read -r name; do
                [[ -n "$name" ]] && printf "    [--] %s\n" "$name"
            done
            echo ""
        fi

        if [[ -n "$UNHEALTHY" ]]; then
            echo "  UNHEALTHY (running):"
            echo -e "$UNHEALTHY" | sort | while read -r name; do
                [[ -n "$name" ]] && printf "    [!!] %s\n" "$name"
            done
            echo ""
        fi

        if [[ -n "$STOPPED" ]]; then
            echo "  Stopped:"
            echo -e "$STOPPED" | sort | while read -r name; do
                [[ -n "$name" ]] && printf "    [XX] %s\n" "$name"
            done
            echo ""
        fi

        if [[ -n "$OTHER" ]]; then
            echo "  Other:"
            echo -e "$OTHER" | sort | while read -r name; do
                [[ -n "$name" ]] && printf "    [??] %s\n" "$name"
            done
            echo ""
        fi
    else
        echo "=== Docker Compose Container Status ==="
        echo ""
        echo "  No containers found."
        echo ""
    fi
fi
