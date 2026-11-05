# shellcheck shell=bash
#
# Przygotowanie macOS. WeasyPrint (cffi.dlopen / ctypes.util.find_library) musi
# znaleźć libgobject-2.0 / pango / harfbuzz / fontconfig zainstalowane przez
# brew. Na Apple Silicon te biblioteki siedzą w /opt/homebrew/lib, którego dyld
# nie konsultuje domyślnie (default search path to /usr/local/lib + /usr/lib).
#
# Próbowaliśmy wcześniej (commit 3531fd2d4) DYLD_FALLBACK_LIBRARY_PATH — nie
# sprawdza się w praktyce: macOS SIP strippuje wszystkie zmienne DYLD_*
# w momencie wywołania chronionej binarki (/usr/bin/*, /bin/sh, itp.), więc
# w łańcuchach typu  make → sh → uv → python → pytest  zmienna regularnie ginie
# po drodze. Z perspektywy pytest/uv vs. dlopen — niedeterministyczne.
#
# Wracamy do symlinków w /usr/local/lib: filesystem-level, dyld konsultuje tę
# ścieżkę z automatu, SIP nic z tym nie zrobi. Wymaga sudo *raz* przy setupie
# maszyny. Idempotentne — nie nadpisuje symlinków wskazujących na te same cele.
#
# UWAGA: To runtime fix dla dlopen. Nie pomaga przy *build-time* błędach
# (np. wheel buduje się ze źródła i nie znajduje cairo.h) — wtedy potrzeba
# PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig + LDFLAGS=-L/opt/homebrew/lib
# + CPPFLAGS=-I/opt/homebrew/include.

require_homebrew() {
    [ -z "$BREW_PREFIX" ] || return 0
    cat >&2 <<'EOF'

BŁĄD: Homebrew (brew) nie jest zainstalowany.

Homebrew jest wymagany do zainstalowania zależności systemowych
(cairo, pango, gdk-pixbuf, libffi, gobject-introspection, gtk+3).

Aby zainstalować Homebrew, uruchom w terminalu poniższe polecenie:

  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

Po zakończeniu instalacji wykonaj kroki dodające 'brew' do PATH
wypisane przez instalator (zwykle dla Apple Silicon: dopisanie
linii 'eval "$(/opt/homebrew/bin/brew shellenv)"' do ~/.zprofile).

Pełna dokumentacja: https://brew.sh

Po instalacji Homebrew uruchom ponownie:  make prepare-developer-machine

EOF
    exit 1
}

# Symlinki w /usr/local/lib — dyld konsultuje tę ścieżkę domyślnie, więc
# niezależnie od stanu DYLD_* (SIP) WeasyPrint znajdzie libki. Homebrew na
# Macach Intel instaluje do /usr/local, więc tam nie ma czego linkować.
link_homebrew_libs() {
    if [ "$BREW_PREFIX" = /usr/local ]; then
        log "Homebrew w /usr/local — symlinki dla dyld nie są potrzebne."
        return
    fi

    if [ ! -d /usr/local/lib ]; then
        echo "Tworzę /usr/local/lib (wymagane sudo)..."
        sudo mkdir -p /usr/local/lib
    fi

    local pair src dst
    for pair in \
        "glib/lib/libgobject-2.0.0.dylib:gobject-2.0" \
        "pango/lib/libpango-1.0.dylib:pango-1.0" \
        "harfbuzz/lib/libharfbuzz.dylib:harfbuzz" \
        "fontconfig/lib/libfontconfig.1.dylib:fontconfig-1" \
        "pango/lib/libpangoft2-1.0.dylib:pangoft2-1.0"; do
        src="$BREW_PREFIX/opt/${pair%:*}"
        dst="/usr/local/lib/${pair##*:}"
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            echo "Symlink $dst już wskazuje na $src — pomijam."
        else
            echo "Tworzę symlink $dst -> $src (wymagane sudo)..."
            sudo ln -sf "$src" "$dst"
        fi
    done
}

# Cleanup po poprzedniej próbie z DYLD_FALLBACK_LIBRARY_PATH — usuń marker
# + linię export z ~/.zprofile, jeśli zostały.
remove_legacy_dyld_entry() {
    local zprofile="$HOME/.zprofile"
    local marker='# bpp: weasyprint dlopen (Homebrew libs on Apple Silicon)'
    if [ -f "$zprofile" ] && grep -qF "$marker" "$zprofile"; then
        cp "$zprofile" "$zprofile.bpp-bak"
        awk -v m="$marker" 'BEGIN{skip=0}
            $0==m {skip=1; next}
            skip>0 {skip--; next}
            {print}' "$zprofile.bpp-bak" >"$zprofile"
        echo "Usunięto stary wpis DYLD_FALLBACK_LIBRARY_PATH z $zprofile" \
            "(backup: $zprofile.bpp-bak)."
    fi
}

prepare_macos() {
    detect_macos
    log "Wykryto: macOS $MACOS_VERSION ($ARCH, Homebrew: ${BREW_PREFIX:-brak})"
    require_homebrew

    log "Instaluję pakiety systemowe"
    brew install cairo pango gdk-pixbuf libffi gobject-introspection gtk+3 node pandoc yarn
    npm install -g grunt-cli
    warn_if_old_node

    ensure_uv
    sync_python_deps
    link_homebrew_libs
    remove_legacy_dyld_entry
    install_playwright_browsers
}
