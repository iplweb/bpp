#!/bin/bash
set -euo pipefail

# bin/scan-deps.sh
#
# Generuje SBOM (CycloneDX) z bieżącego projektu, a następnie skanuje go
# OSV-Scanner-em (Google) i Grype (Anchore) szukając znanych CVE.
#
# Default: skan deps PRODUKCYJNYCH (uv export --no-dev) - to co realnie
# trafia do obrazu Dockera.
#
# --full: skan bieżącego venva ze wszystkimi extras (dev/test/docs).
# Pokazuje też CVE w ipython, pytest, sphinx itd. - przydatne tylko
# jeśli chcesz wiedzieć co dotyka developerów lokalnie. Te paczki
# nigdy nie idą do obrazu produkcyjnego.

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
BOLD=$'\033[1m'
NC=$'\033[0m'

SCRIPT_NAME=$(basename "$0")
WORK_DIR="${TMPDIR:-/tmp}/bpp-sbom"
SBOM_PATH="${WORK_DIR}/sbom.json"

MODE="prod"
SEVERITY_FILTER="HIGH,CRITICAL"
RUN_OSV=true
RUN_GRYPE=true
RUN_TRIVY=true
GATE=true
KEEP_TMP=false
TOTAL_FINDINGS=0

usage() {
    cat << EOF
${BOLD}Skan zależności BPP pod kątem CVE${NC}

${YELLOW}Użycie:${NC}
    $SCRIPT_NAME [opcje]

${YELLOW}Opcje:${NC}
    --full           Skanuj cały venv (z [dev] extras), nie tylko prod
    --all-severity   Pokaż wszystkie severity (default: HIGH/CRITICAL)
    --no-osv         Pomiń OSV-Scanner
    --no-grype       Pomiń Grype
    --no-trivy       Pomiń Trivy
    --no-gate        Nie failuj na findings (tylko raport, exit 0)
    --keep           Nie kasuj ${WORK_DIR} po zakończeniu
    -h, --help       Pokaż tę pomoc

${YELLOW}Tryb gate (domyślny):${NC}
    Skrypt zwraca exit 1 jeśli któryś skaner znajdzie HIGH/CRITICAL CVE.
    To pozwala wpiąć go jako pre-release guard (make new-release zatrzyma
    się przed pushem, jeśli coś dramatycznego). Wyłącz przez --no-gate
    (tylko raport) — sensowne dla scheduled scanów / debugowania.

${YELLOW}Wymagane narzędzia:${NC}
    uv, uvx, jq         (powinny już być)
    osv-scanner         brew install osv-scanner
    grype               brew install grype
    trivy               brew install trivy

${YELLOW}Przykłady:${NC}
    $SCRIPT_NAME                    # Prod-only, HIGH/CRITICAL, gate
    $SCRIPT_NAME --full             # Cały venv włącznie z dev extras
    $SCRIPT_NAME --all-severity     # Także LOW/MEDIUM
    $SCRIPT_NAME --no-gate          # Raport bez blokowania exit-em
    $SCRIPT_NAME --no-trivy --no-grype  # Tylko OSV-Scanner

${YELLOW}Wynik:${NC}
    SBOM:  ${WORK_DIR}/sbom.json
    OSV:   ${WORK_DIR}/osv-report.json
    Grype: ${WORK_DIR}/grype-report.json
    Trivy: ${WORK_DIR}/trivy-report.json
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)          MODE="full"; shift ;;
        --all-severity)  SEVERITY_FILTER=""; shift ;;
        --no-osv)        RUN_OSV=false; shift ;;
        --no-grype)      RUN_GRYPE=false; shift ;;
        --no-trivy)      RUN_TRIVY=false; shift ;;
        --no-gate)       GATE=false; shift ;;
        --keep)          KEEP_TMP=true; shift ;;
        -h|--help)       usage; exit 0 ;;
        *) echo -e "${RED}Nieznana opcja: $1${NC}" >&2; usage; exit 2 ;;
    esac
done

require() {
    local cmd=$1; local hint=$2
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}✗ Brak narzędzia: ${BOLD}${cmd}${NC}" >&2
        echo -e "  Zainstaluj: ${YELLOW}${hint}${NC}" >&2
        return 1
    fi
}

missing=0
require uv  "https://docs.astral.sh/uv/" || missing=1
require uvx "część instalacji uv"        || missing=1
require jq  "brew install jq"            || missing=1
$RUN_OSV   && { require osv-scanner "brew install osv-scanner" || missing=1; }
$RUN_GRYPE && { require grype       "brew install grype"       || missing=1; }
$RUN_TRIVY && { require trivy       "brew install trivy"       || missing=1; }
[[ $missing -ne 0 ]] && exit 3

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p "$WORK_DIR"
trap '[[ "$KEEP_TMP" == false ]] || echo -e "${BLUE}Pliki zostają w: ${WORK_DIR}${NC}"' EXIT

echo -e "${BOLD}${BLUE}=== 1/4 Generuję SBOM (${MODE}) ===${NC}"

if [[ "$MODE" == "prod" ]]; then
    REQ_PATH="${WORK_DIR}/requirements.txt"
    uv export --no-dev --format requirements-txt --no-hashes --quiet -o "$REQ_PATH"
    # cyclonedx-py requirements odczyta plik i wyprodukuje SBOM
    uvx --quiet --from cyclonedx-bom cyclonedx-py requirements \
        "$REQ_PATH" \
        --output-reproducible \
        --output-format JSON \
        --output-file "$SBOM_PATH" \
        --pyproject pyproject.toml
else
    # Skan bieżącego venva. Wymaga uv sync żeby venv był aktualny.
    [[ -d .venv ]] || { echo -e "${RED}Brak .venv. Uruchom 'uv sync --all-extras' najpierw.${NC}" >&2; exit 4; }
    uvx --quiet --from cyclonedx-bom cyclonedx-py environment \
        .venv \
        --output-reproducible \
        --output-format JSON \
        --output-file "$SBOM_PATH"
fi

PKG_COUNT=$(jq '.components | length' "$SBOM_PATH")
echo -e "${GREEN}✓ SBOM: $SBOM_PATH (${PKG_COUNT} pakietów)${NC}"
echo

if $RUN_OSV; then
    echo -e "${BOLD}${BLUE}=== 2/4 OSV-Scanner (Google) ===${NC}"
    OSV_REPORT="${WORK_DIR}/osv-report.json"
    set +e
    osv-scanner scan source --sbom="$SBOM_PATH" \
        --format=json --output="$OSV_REPORT" 2>/dev/null
    osv_exit=$?
    set -e

    if [[ -s "$OSV_REPORT" ]]; then
        OSV_VULNS=$(jq '[.results[]?.packages[]?.vulnerabilities[]?] | length' "$OSV_REPORT" 2>/dev/null || echo 0)
    else
        OSV_VULNS=0
    fi

    if [[ "$OSV_VULNS" -gt 0 ]]; then
        TOTAL_FINDINGS=$((TOTAL_FINDINGS + OSV_VULNS))
        echo -e "${YELLOW}⚠ Znaleziono ${OSV_VULNS} CVE${NC}"
        # Skrótowy widok: package, version, CVE id, severity
        jq -r '
            .results[]? | .packages[]? |
            . as $p |
            .vulnerabilities[]? |
            "\($p.package.name)@\($p.package.version)\t\(.id)\t\((.database_specific.severity // "?"))"
        ' "$OSV_REPORT" | sort -u | column -t -s $'\t'
    else
        echo -e "${GREEN}✓ Brak znanych CVE${NC}"
    fi
    echo -e "  raport: ${OSV_REPORT}"
    echo
fi

if $RUN_GRYPE; then
    echo -e "${BOLD}${BLUE}=== 3/4 Grype (Anchore) ===${NC}"
    GRYPE_REPORT="${WORK_DIR}/grype-report.json"

    GRYPE_ARGS=("sbom:${SBOM_PATH}" -o json --file "$GRYPE_REPORT")
    if [[ -n "$SEVERITY_FILTER" ]]; then
        # Grype: --fail-on filter; my chcemy tylko output, więc filter na jq.
        :
    fi

    set +e
    grype "${GRYPE_ARGS[@]}" >/dev/null 2>&1
    grype_exit=$?
    set -e

    if [[ -s "$GRYPE_REPORT" ]]; then
        if [[ -n "$SEVERITY_FILTER" ]]; then
            FILTER=$(echo "$SEVERITY_FILTER" | tr ',' '|')
            GRYPE_VULNS=$(jq --arg f "$FILTER" \
                '[.matches[]? | select(.vulnerability.severity | test("^(" + $f + ")$"; "i"))] | length' \
                "$GRYPE_REPORT")
        else
            GRYPE_VULNS=$(jq '[.matches[]?] | length' "$GRYPE_REPORT")
        fi

        if [[ "$GRYPE_VULNS" -gt 0 ]]; then
            TOTAL_FINDINGS=$((TOTAL_FINDINGS + GRYPE_VULNS))
            echo -e "${YELLOW}⚠ Znaleziono ${GRYPE_VULNS} CVE (filter: ${SEVERITY_FILTER:-wszystkie})${NC}"
            if [[ -n "$SEVERITY_FILTER" ]]; then
                FILTER=$(echo "$SEVERITY_FILTER" | tr ',' '|')
                jq -r --arg f "$FILTER" '
                    .matches[]? |
                    select(.vulnerability.severity | test("^(" + $f + ")$"; "i")) |
                    "\(.artifact.name)@\(.artifact.version)\t\(.vulnerability.id)\t\(.vulnerability.severity)\t\(.vulnerability.fix.versions[]? // "no-fix")"
                ' "$GRYPE_REPORT" | sort -u | column -t -s $'\t'
            else
                jq -r '
                    .matches[]? |
                    "\(.artifact.name)@\(.artifact.version)\t\(.vulnerability.id)\t\(.vulnerability.severity)\t\(.vulnerability.fix.versions[]? // "no-fix")"
                ' "$GRYPE_REPORT" | sort -u | column -t -s $'\t'
            fi
        else
            echo -e "${GREEN}✓ Brak CVE (filter: ${SEVERITY_FILTER})${NC}"
        fi
        echo -e "  raport: ${GRYPE_REPORT}"
    else
        echo -e "${RED}✗ Grype nie wygenerował raportu (exit ${grype_exit})${NC}"
    fi
    echo
fi

if $RUN_TRIVY; then
    echo -e "${BOLD}${BLUE}=== 4/4 Trivy (Aqua Security) ===${NC}"
    TRIVY_REPORT="${WORK_DIR}/trivy-report.json"

    TRIVY_ARGS=(sbom "$SBOM_PATH" --format json --output "$TRIVY_REPORT" --quiet)
    # --ignore-unfixed: nie raportujemy CVE bez dostępnego fixa (zgodnie
    # z polityką w build-docker-images.yml). HIGH/CRITICAL filter na jq.
    TRIVY_ARGS+=(--ignore-unfixed)
    if [[ -n "$SEVERITY_FILTER" ]]; then
        TRIVY_ARGS+=(--severity "$SEVERITY_FILTER")
    fi

    set +e
    trivy "${TRIVY_ARGS[@]}" 2>/dev/null
    trivy_exit=$?
    set -e

    if [[ -s "$TRIVY_REPORT" ]]; then
        TRIVY_VULNS=$(jq '[.Results[]?.Vulnerabilities[]?] | length' "$TRIVY_REPORT" 2>/dev/null || echo 0)

        if [[ "$TRIVY_VULNS" -gt 0 ]]; then
            TOTAL_FINDINGS=$((TOTAL_FINDINGS + TRIVY_VULNS))
            echo -e "${YELLOW}⚠ Znaleziono ${TRIVY_VULNS} CVE (filter: ${SEVERITY_FILTER:-wszystkie}, --ignore-unfixed)${NC}"
            jq -r '
                .Results[]? | .Vulnerabilities[]? |
                "\(.PkgName)@\(.InstalledVersion)\t\(.VulnerabilityID)\t\(.Severity)\t\(.FixedVersion // "no-fix")"
            ' "$TRIVY_REPORT" | sort -u | column -t -s $'\t'
        else
            echo -e "${GREEN}✓ Brak CVE (filter: ${SEVERITY_FILTER:-wszystkie}, --ignore-unfixed)${NC}"
        fi
        echo -e "  raport: ${TRIVY_REPORT}"
    else
        echo -e "${RED}✗ Trivy nie wygenerował raportu (exit ${trivy_exit})${NC}"
    fi
    echo
fi

echo -e "${BOLD}${BLUE}=== Podsumowanie ===${NC}"
if [[ "$TOTAL_FINDINGS" -gt 0 ]]; then
    echo -e "${YELLOW}⚠ Łącznie ${TOTAL_FINDINGS} findings (suma ze skanerów; może zawierać duplikaty tej samej CVE)${NC}"
    if $GATE; then
        echo -e "${RED}${BOLD}✗ Gate: BLOKADA. Napraw vulnerabilities albo użyj --no-gate.${NC}"
        echo -e "  Pliki w: ${BLUE}${WORK_DIR}${NC}"
        exit 1
    else
        echo -e "${YELLOW}--no-gate aktywne: zwracam exit 0 mimo findings${NC}"
    fi
else
    echo -e "${GREEN}${BOLD}✓ Brak findings — czysto.${NC}"
fi
echo -e "${BOLD}${GREEN}Gotowe.${NC} Pliki w: ${BLUE}${WORK_DIR}${NC}"
