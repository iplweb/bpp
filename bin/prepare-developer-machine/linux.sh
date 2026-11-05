# shellcheck shell=bash
#
# Przygotowanie Linuksa. Listy pakietów idą za docker/bpp_base/build.txt:
# python-ldap jest tylko jako sdist, a `--all-extras` go wciąga, więc `uv sync`
# kompiluje go lokalnie i potrzebuje kompilatora oraz nagłówków LDAP/SASL/SSL
# (bez nich: `fatal error: lber.h: No such file or directory`).

SUDO=""

setup_sudo() {
    if [ "$(id -u)" -ne 0 ]; then
        command -v sudo >/dev/null 2>&1 || die "Uruchom jako root albo doinstaluj sudo."
        SUDO=sudo
    fi
}

# Wypisuje pierwszy z pakietów dostępny w repozytoriach apt: niektóre nazwy
# różnią się między wersjami Debiana i Ubuntu.
apt_first_available() {
    local package
    for package in "$@"; do
        if apt-cache show --no-all-versions "$package" 2>/dev/null |
            grep -q "^Package: $package\$"; then
            printf '%s\n' "$package"
            return
        fi
    done
    die "Żaden z pakietów nie jest dostępny w apt: $*"
}

install_packages_debian() {
    $SUDO apt-get update

    # Osobne przypisania: `die` w podpowłoce wewnątrz argumentów polecenia
    # nie przerwałoby skryptu.
    local gdk_pixbuf girepository
    gdk_pixbuf="$(apt_first_available libgdk-pixbuf2.0-dev \
        libgdk-pixbuf-xlib-2.0-dev libgdk-pixbuf-2.0-dev)"
    girepository="$(apt_first_available libgirepository1.0-dev libgirepository-2.0-dev)"

    $SUDO apt-get install -y \
        build-essential ca-certificates curl gettext git \
        nodejs npm pandoc python3-dev \
        libcairo2-dev libffi-dev libgtk-3-dev libldap2-dev libpango1.0-dev \
        libpq-dev libsasl2-dev libssl-dev \
        "$gdk_pixbuf" "$girepository"
    # Yarn z npm, nie z apt: pakiet `yarnpkg` ma różne wersje główne między
    # dystrybucjami (Ubuntu 26.04: 4.1.0). Binarka npm w /usr/local/bin
    # przesłania też `yarnpkg` z apt zainstalowany wcześniej.
    $SUDO npm install -g grunt-cli "yarn@$YARN_VERSION"
}

install_packages_fedora() {
    # Na RHEL i pochodnych część pakietów -devel siedzi w repozytorium CRB.
    if [ "$LINUX_ID" != fedora ]; then
        $SUDO dnf install -y dnf-plugins-core
        $SUDO dnf config-manager --set-enabled crb
    fi
    # pandoc (eksport DOCX) jest w repozytoriach Fedory; na RHEL i
    # pochodnych tylko w EPEL, więc tam brak pakietu nie przerywa instalacji.
    if ! $SUDO dnf install -y pandoc; then
        warn "Nie udało się zainstalować pandoc (na RHEL włącz EPEL)." \
            "Bez niego eksport DOCX przejdzie na fallback html2docx."
    fi
    $SUDO dnf install -y \
        ca-certificates curl gcc gcc-c++ gettext git make \
        nodejs npm python3-devel \
        cairo-devel cyrus-sasl-devel gdk-pixbuf2-devel \
        gobject-introspection-devel gtk3-devel libffi-devel libpq-devel \
        openldap-devel openssl-devel pango-devel \
        alsa-lib at-spi2-atk atk cups-libs libXcomposite libXdamage \
        libXrandr libdrm mesa-libgbm nss
    # npm daje też `yarnpkg`, którego szuka Makefile (YARN_CMD na Linuksie).
    $SUDO npm install -g grunt-cli "yarn@$YARN_VERSION"
}

install_packages_arch() {
    $SUDO pacman -Syu --needed --noconfirm \
        base-devel ca-certificates curl gettext git \
        nodejs npm pandoc-cli python \
        cairo cyrus-sasl gdk-pixbuf2 gobject-introspection gtk3 libffi \
        libldap openssl pango postgresql-libs \
        alsa-lib at-spi2-core libcups libdrm libxcomposite libxdamage \
        libxrandr mesa nss
    $SUDO npm install -g grunt-cli "yarn@$YARN_VERSION"
}

# Makefile wywołuje `yarnpkg` przez PATH, więc sprawdzamy tę samą binarkę.
verify_yarnpkg() {
    local current
    current="$(yarnpkg --version)"
    if [ "$current" != "$YARN_VERSION" ]; then
        die "yarnpkg z PATH ($(command -v yarnpkg)) ma wersję $current," \
            "a projekt wymaga $YARN_VERSION. Sprawdź kolejność katalogów w PATH."
    fi
    log "yarnpkg $current"
}

prepare_linux() {
    detect_linux
    log "Wykryto: $LINUX_NAME ($ARCH, rodzina: ${LINUX_FAMILY:-nieznana})"

    if [ -z "$LINUX_FAMILY" ]; then
        die "Nieobsługiwana dystrybucja: $LINUX_ID. Obsługiwane: rodziny" \
            "Debiana (apt), Fedory/RHEL (dnf) i Archa (pacman). Na innych" \
            "zainstaluj odpowiedniki bibliotek z bin/prepare-developer-machine/linux.sh."
    fi

    setup_sudo
    log "Instaluję pakiety systemowe"
    "install_packages_$LINUX_FAMILY"
    warn_if_old_node
    verify_yarnpkg

    ensure_uv
    sync_python_deps
    install_playwright_browsers
}
