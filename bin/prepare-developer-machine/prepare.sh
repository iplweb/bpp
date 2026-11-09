#!/usr/bin/env bash
#
# Przygotowanie maszyny deweloperskiej: rozpoznaje system (macOS, dystrybucja
# Linuksa) i instaluje pakiety systemowe, uv, zależności Pythona oraz
# przeglądarki Playwright.
#
# Wywoływane przez targety Makefile:
#   make prepare-developer-machine        # auto-detekcja systemu
#   make prepare-developer-machine-macos  # wymuszenie wariantu
#   make prepare-developer-machine-linux
#   make playwright-install               # tylko przeglądarki Playwright
#   make playwright-check                 # czy przeglądarki są (bez instalacji)
#
# Zmienne środowiskowe:
#   OS_RELEASE_FILE  plik zamiast /etc/os-release (testy detekcji dystrybucji)

set -euo pipefail

usage() {
    cat <<'EOF'
Użycie:
  bin/prepare-developer-machine/prepare.sh [auto|macos|linux]
  bin/prepare-developer-machine/prepare.sh playwright
  bin/prepare-developer-machine/prepare.sh playwright-check
  bin/prepare-developer-machine/prepare.sh detect

auto        Rozpoznaje system i uruchamia właściwy wariant (domyślnie).
macos       Homebrew + uv + uv sync + symlinki dla WeasyPrint + Playwright.
linux       apt/dnf/pacman + uv + uv sync + Playwright.
playwright  Tylko przeglądarki Playwright (po wcześniejszym uv sync).
playwright-check
            Sprawdza, czy przeglądarki Playwright są zainstalowane
            (bez sudo i sieci); kod 1 + podpowiedź, gdy ich brak.
detect      Wypisuje rozpoznany system i niczego nie instaluje.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=bin/prepare-developer-machine/lib.sh
. "$SCRIPT_DIR/lib.sh"
# shellcheck source=bin/prepare-developer-machine/linux.sh
. "$SCRIPT_DIR/linux.sh"
# shellcheck source=bin/prepare-developer-machine/macos.sh
. "$SCRIPT_DIR/macos.sh"

print_detected() {
    detect_os
    if [ "$DETECTED_OS" = macos ]; then
        detect_macos
        echo "os=macos version=$MACOS_VERSION arch=$ARCH" \
            "brew_prefix=${BREW_PREFIX:-none}"
    else
        detect_linux
        echo "os=linux id=$LINUX_ID version=${LINUX_VERSION_ID:-none}" \
            "arch=$ARCH family=${LINUX_FAMILY:-unsupported}"
    fi
}

# Wymuszony wariant też musi pasować do systemu: apt na macOS albo brew na
# Linuksie skończyłyby się mylącym błędem w połowie instalacji.
run_variant() {
    detect_os
    if [ "$1" != auto ] && [ "$1" != "$DETECTED_OS" ]; then
        die "Wariant $1 nie pasuje do tego systemu ($DETECTED_OS)."
    fi
    "prepare_$DETECTED_OS"
}

main() {
    local command="${1:-auto}"
    cd "$REPO_ROOT"

    case "$command" in
        auto | macos | linux) run_variant "$command" ;;
        playwright) install_playwright_browsers ;;
        playwright-check) check_playwright_browsers ;;
        detect) print_detected ;;
        -h | --help | help) usage ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"
