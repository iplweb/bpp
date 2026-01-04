#!/bin/bash
set -euo pipefail

# Kolory dla wyjscia
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_NAME=$(basename "$0")

# Domyslne wartosci
DRY_RUN=false
FORCE=false
VERBOSE=false
YES=false

usage() {
    cat << EOF
${BLUE}Kasowanie baz danych PostgreSQL pasujacych do wzorca${NC}

${YELLOW}Uzycie:${NC}
    $SCRIPT_NAME [opcje] <prefiks>

${YELLOW}Argumenty:${NC}
    <prefiks>    Prefiks nazwy bazy danych (np. "bpp_UML" skasuje bpp_UML_*)
                 Prefiks musi zaczynac sie od "bpp_" lub "test_bpp"
                 Baza "bpp" (bez podkreslenia) nigdy nie zostanie skasowana.

${YELLOW}Opcje:${NC}
    -n, --dry-run    Tylko pokaz co zostaloby skasowane (bez kasowania)
    -f, --force      Wymus rozlaczenie aktywnych polaczen przed kasowaniem
    -y, --yes        Nie pytaj o potwierdzenie (dla skryptow)
    -v, --verbose    Wiecej informacji podczas dzialania
    -h, --help       Pokaz te pomoc

${YELLOW}Przyklady:${NC}
    $SCRIPT_NAME bpp_UML           # Kasuje bpp_UML_*
    $SCRIPT_NAME -n bpp_APoż       # Podglad - co zostaloby skasowane
    $SCRIPT_NAME -f bpp_PIWet-PIB  # Kasuje z wymuszonym rozlaczeniem
    $SCRIPT_NAME -f -y test_bpp    # Kasuje test_bpp* bez pytania

${YELLOW}Bezpieczenstwo:${NC}
    - Prefiks MUSI zaczynac sie od "bpp_" lub "test_bpp"
    - Baza "bpp" (glowna) nigdy nie zostanie skasowana
    - Uzyj --dry-run aby sprawdzic przed kasowaniem

EOF
    exit 0
}

error() {
    echo -e "${RED}BLAD:${NC} $1" >&2
    exit 1
}

warn() {
    echo -e "${YELLOW}UWAGA:${NC} $1" >&2
}

info() {
    echo -e "${GREEN}INFO:${NC} $1"
}

debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}DEBUG:${NC} $1"
    fi
}

# Parsowanie argumentow
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -y|--yes)
            YES=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            error "Nieznana opcja: $1\nUzyj '$SCRIPT_NAME --help' aby zobaczyc dostepne opcje."
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Sprawdz czy podano prefiks
if [ ${#POSITIONAL_ARGS[@]} -eq 0 ]; then
    error "Brak prefiksu!\n\nUzyj '$SCRIPT_NAME --help' aby zobaczyc pomoc."
fi

if [ ${#POSITIONAL_ARGS[@]} -gt 1 ]; then
    error "Podano zbyt wiele argumentow. Oczekiwano jednego prefiksu."
fi

PREFIX="${POSITIONAL_ARGS[0]}"

# Walidacja prefiksu - MUSI zaczynac sie od "bpp_" lub "test_bpp"
if [[ ! "$PREFIX" =~ ^(bpp_|test_bpp) ]]; then
    error "Prefiks musi zaczynac sie od 'bpp_' lub 'test_bpp'!\n\nPodano: '$PREFIX'\nPrawidlowe przyklady: 'bpp_UML', 'bpp_APoż', 'test_bpp'"
fi

# Dodatkowe zabezpieczenie - prefiks nie moze byc dokladnie "bpp_"
if [ "$PREFIX" = "bpp_" ]; then
    error "Prefiks 'bpp_' jest zbyt ogolny i skasowalby wszystkie bazy!\nPodaj bardziej szczegolowy prefiks, np. 'bpp_UML', 'bpp_APoż'."
fi

debug "Prefiks: $PREFIX"
debug "Dry run: $DRY_RUN"
debug "Force: $FORCE"

# Wzorzec SQL LIKE (PREFIX% zeby zlapac tez sam prefiks, np. test_bpp)
PATTERN="${PREFIX}%"
debug "Wzorzec SQL LIKE: $PATTERN"

# Pobierz liste baz danych
DATABASES=$(psql -t -A -c "SELECT datname FROM pg_database WHERE datname LIKE '$PATTERN' ORDER BY datname")

if [ -z "$DATABASES" ]; then
    info "Nie znaleziono baz danych pasujacych do wzorca '${PATTERN}'"
    exit 0
fi

# Policz bazy
DB_COUNT=$(echo "$DATABASES" | wc -l | tr -d ' ')

echo ""
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}=== TRYB PODGLADU (dry-run) ===${NC}"
    echo -e "Nastepujace bazy danych ${BLUE}zostalyby skasowane${NC}:"
else
    echo -e "${RED}=== KASOWANIE BAZ DANYCH ===${NC}"
    echo -e "Nastepujace bazy danych ${RED}zostana skasowane${NC}:"
fi
echo ""

# Wyswietl liste baz
while IFS= read -r db; do
    echo "  - $db"
done <<< "$DATABASES"

echo ""
echo -e "Lacznie: ${BLUE}$DB_COUNT${NC} baz(y) danych"
echo ""

# W trybie dry-run konczymy tutaj
if [ "$DRY_RUN" = true ]; then
    echo -e "${GREEN}Aby skasowac te bazy, uruchom bez opcji --dry-run${NC}"
    exit 0
fi

# Potwierdzenie przed kasowaniem (pomijane z -y/--yes)
if [ "$YES" != true ]; then
    echo -e "${YELLOW}Czy na pewno chcesz skasowac te bazy danych? [t/N]${NC} "
    read -r CONFIRM

    if [[ ! "$CONFIRM" =~ ^[tTyY]$ ]]; then
        echo "Anulowano."
        exit 0
    fi
fi

echo ""

# Kasowanie baz
DROPDB_OPTS=""
if [ "$FORCE" = true ]; then
    DROPDB_OPTS="-f"
fi

SUCCESS_COUNT=0
FAIL_COUNT=0

while IFS= read -r db; do
    # Dodatkowe zabezpieczenie - nigdy nie kasuj "bpp"
    if [ "$db" = "bpp" ]; then
        warn "Pominieto baze 'bpp' (zabezpieczenie)"
        continue
    fi

    echo -n "Kasowanie: $db ... "

    if dropdb $DROPDB_OPTS "$db" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        ((SUCCESS_COUNT++))
    else
        echo -e "${RED}BLAD${NC}"
        ((FAIL_COUNT++))
        if [ "$FORCE" != true ]; then
            warn "Sprobuj z opcja -f (--force) aby wymusic rozlaczenie polaczen"
        fi
    fi
done <<< "$DATABASES"

echo ""
echo -e "Zakonczone: ${GREEN}$SUCCESS_COUNT${NC} skasowano, ${RED}$FAIL_COUNT${NC} bledow"
