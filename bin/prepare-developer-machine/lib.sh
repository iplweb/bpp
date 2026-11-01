# shellcheck shell=bash disable=SC2034
#
# Wspólne funkcje skryptów prepare-developer-machine: logowanie, detekcja
# systemu, instalacja uv i przeglądarek Playwright.
#
# UWAGA: macOS ma bash 3.2 — bez tablic asocjacyjnych, `${x,,}` i `mapfile`.

# Trzymaj w parze z pinem uv w CI (`version:` w setup-uv), Dockerfile
# (`COPY --from=ghcr.io/astral-sh/uv:…`) i .pre-commit-config.yaml. Inna wersja
# potrafi uznać ten sam uv.lock za nieaktualny.
UV_VERSION="0.13.5"

# SHA-256 instalatora tej wersji uv (install.sh z astral.sh jest identyczny
# z uv-installer.sh z GitHub Releases). Instalator ma wpisane sumy binarek,
# więc jeden hash wystarcza na wszystkie platformy. Podbijając UV_VERSION,
# policz nowy: curl -LsSf https://astral.sh/uv/<wersja>/install.sh | sha256sum
UV_INSTALLER_SHA256="1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a"

# yarn.lock jest w formacie v1, czyli Yarn Classic.
YARN_VERSION="1.22.22"

# Node z obrazów Dockera to 24 (NODEJS_VERSION w docker/bpp_base/Dockerfile).
MIN_NODE_MAJOR=20

log() { printf '\n==> %s\n' "$*"; }
warn() { printf 'UWAGA: %s\n' "$*" >&2; }
die() {
    printf 'BŁĄD: %s\n' "$*" >&2
    exit 1
}

# Ustawia DETECTED_OS na `macos` albo `linux`.
detect_os() {
    case "$(uname -s)" in
        Darwin) DETECTED_OS=macos ;;
        Linux) DETECTED_OS=linux ;;
        *) die "Nieobsługiwany system: $(uname -s). Obsługiwane: macOS, Linux." ;;
    esac
}

# Ustawia MACOS_VERSION, ARCH i BREW_PREFIX (pusty, gdy nie ma Homebrew).
detect_macos() {
    MACOS_VERSION="$(sw_vers -productVersion)"
    ARCH="$(uname -m)"
    BREW_PREFIX=""
    if command -v brew >/dev/null 2>&1; then
        BREW_PREFIX="$(brew --prefix)"
    fi
}

# Ustawia LINUX_ID, LINUX_VERSION_ID, LINUX_NAME, ARCH i LINUX_FAMILY
# (`debian`, `fedora`, `arch` albo pusty, gdy dystrybucja jest nieobsługiwana).
# ID_LIKE pozwala rozpoznać pochodne: Mint, Pop!_OS, Rocky, Manjaro itd.
detect_linux() {
    local os_release="${OS_RELEASE_FILE:-/etc/os-release}"
    [ -r "$os_release" ] || die "Brak $os_release — nie rozpoznam dystrybucji."

    local ID="" ID_LIKE="" VERSION_ID="" PRETTY_NAME=""
    # shellcheck disable=SC1090
    . "$os_release"

    LINUX_ID="$ID"
    LINUX_VERSION_ID="$VERSION_ID"
    LINUX_NAME="${PRETTY_NAME:-$ID}"
    ARCH="$(uname -m)"
    LINUX_FAMILY=""

    local candidate
    for candidate in $ID $ID_LIKE; do
        case "$candidate" in
            debian | ubuntu) LINUX_FAMILY=debian ;;
            fedora | rhel | centos) LINUX_FAMILY=fedora ;;
            arch) LINUX_FAMILY=arch ;;
        esac
        [ -z "$LINUX_FAMILY" ] || break
    done
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# Pobiera instalator uv do pliku i uruchamia go dopiero po sprawdzeniu sumy.
install_uv() {
    local installer actual
    installer="$(mktemp)"
    if ! curl -LsSf --proto '=https' --tlsv1.2 -o "$installer" \
        "https://astral.sh/uv/${UV_VERSION}/install.sh"; then
        rm -f "$installer"
        die "Nie udało się pobrać instalatora uv $UV_VERSION."
    fi

    actual="$(sha256_of "$installer")"
    if [ "$actual" != "$UV_INSTALLER_SHA256" ]; then
        rm -f "$installer"
        die "Zła suma SHA-256 instalatora uv $UV_VERSION: $actual" \
            "(oczekiwana: $UV_INSTALLER_SHA256). Instalator NIE został uruchomiony."
    fi

    sh "$installer"
    rm -f "$installer"
}

# Przypina uv, gdy go nie ma; instalator z astral.sh trafia do ~/.local/bin.
# Na PATH dokładamy ten katalog zawsze, żeby znaleźć uv z poprzedniego
# uruchomienia, gdy shell nie wczytał jeszcze zmienionego profilu.
ensure_uv() {
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv >/dev/null 2>&1; then
        local current
        current="$(uv --version | awk '{print $2}')"
        if [ "$current" = "$UV_VERSION" ]; then
            log "uv $current już zainstalowane — pomijam."
        else
            warn "uv $current różni się od wersji projektu ($UV_VERSION)."
            warn "Zaktualizuj: uv self update $UV_VERSION"
        fi
        return
    fi

    command -v curl >/dev/null 2>&1 || die "Do instalacji uv potrzebny jest curl."
    log "Instaluję uv $UV_VERSION"
    install_uv
    command -v uv >/dev/null 2>&1 ||
        die "uv zainstalowane, ale nie ma go na PATH (sprawdź ~/.local/bin)."
    warn "uv jest w ~/.local/bin — otwórz nowy shell, żeby było na PATH."
}

sync_python_deps() {
    log "Synchronizuję zależności Pythona"
    uv sync --frozen --no-install-project --all-extras
}

warn_if_old_node() {
    local major
    major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
    if [ "$major" -lt "$MIN_NODE_MAJOR" ]; then
        warn "Node $major jest stary (obrazy Dockera używają 24)."
        warn "\`make assets\` może się nie udać — doinstaluj nowszy Node."
    fi
}

# Wymaga wcześniejszego `uv sync --all-extras` (playwright CLI siedzi w grupie
# dev). `--with-deps` doinstalowuje biblioteki systemowe przez apt (sudo),
# więc działa tylko na rodzinie Debiana. Na macOS przeglądarki są
# samowystarczalne, a na Fedorze/Archu biblioteki instaluje linux.sh.
# Tylko Chromium Headless Shell: testy nie używają Firefoksa ani WebKita, a CI
# instaluje to samo (docker/bpp_base/Dockerfile). Pełny Chromium jest potrzebny
# wyłącznie do `pytest --headed`: `uv run playwright install chromium`.
install_playwright_browsers() {
    export PATH="$HOME/.local/bin:$PATH"
    detect_os

    log "Instaluję przeglądarki Playwright"
    if [ "$DETECTED_OS" = linux ]; then
        detect_linux
        if [ "$LINUX_FAMILY" = debian ]; then
            uv run playwright install --with-deps --only-shell chromium
            return
        fi
        warn "Playwright oficjalnie wspiera tylko Debiana i Ubuntu."
    fi
    uv run playwright install --only-shell chromium
}
