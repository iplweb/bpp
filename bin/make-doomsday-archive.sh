#!/usr/bin/env bash
#
# make-doomsday-archive.sh — snapshot WSZYSTKICH źródeł, od których zależy BPP.
#
# Buduje samowystarczalne, kryptograficznie weryfikowalne archiwum na wypadek
# "doomsday" (PyPI/npm znika, fork z GitHub jest kasowany, wersja yanked).
#
# Produkuje DWA artefakty (zgodnie z ustaleniami):
#
#   A) ŹRÓDŁA (warstwy 1-4) — odbudowywalne na dowolnym przyszłym OS-ie:
#        1. kod BPP            → git bundle (pełna historia, nie checkout)
#        2. źródła Python      → sdist (źródła) + wheels (host + linux-prod)
#        3. źródła JavaScript  → yarn v1 offline mirror (.tgz każdej paczki)
#        4. forki git          → git clone --mirror (pełna historia)
#
#   B) WARSTWA SYSTEMOWA (warstwa 5) — zamraża też OS/interpreter/libpq:
#        5. obrazy Docker      → docker save (best-effort; --no-docker wyłącza)
#
# Lockfile to PRZEPIS; ten skrypt ściąga SKŁADNIKI (bajty) i zapisuje
# MANIFEST.sha256, żeby za 10 lat zweryfikować, że nic nie zgniło.
#
# UŻYCIE:
#   bin/make-doomsday-archive.sh [OUT_DIR]      # zbuduj archiwum
#   bin/make-doomsday-archive.sh --verify DIR   # zweryfikuj MANIFEST.sha256
#
# ZMIENNE ŚRODOWISKOWE:
#   BPP_PYVER=3.12                  wersja Pythona dla wheeli linux-prod
#   BPP_IMAGES="img:tag img2:tag"   obrazy Docker do docker save
#   BPP_NO_DOCKER=1  /  --no-docker pomiń warstwę 5
#   BPP_NO_TARBALL=1 /  --no-tar    nie pakuj na końcu w .tar.zst
#
# Skrypt jest IDEMPOTENTNY na poziomie kroków: każdy krok ma własny podkatalog
# i nadpisuje swój wynik. Kroki redundantne (wheels, docker) są best-effort —
# częściowy wynik + log mówią prawdę; krok krytyczny (sdist, mirror) głośno
# ostrzega, ale nie wywala całości, żeby pół-archiwum > brak archiwum.

set -euo pipefail

# ── lokalizacje ──────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYVER="${BPP_PYVER:-3.12}"
PYTAG="cp${PYVER//./}"                    # 3.12 → cp312
DEFAULT_IMAGES="iplweb/bpp_appserver:latest iplweb/bpp_dbserver:latest"
IMAGES="${BPP_IMAGES:-$DEFAULT_IMAGES}"

# ── logowanie ────────────────────────────────────────────────────────────────
c_info()  { printf '\033[1;34m▶ %s\033[0m\n'  "$*"; }
c_ok()    { printf '\033[1;32m✓ %s\033[0m\n'  "$*"; }
c_warn()  { printf '\033[1;33m⚠ %s\033[0m\n'  "$*" >&2; }
c_err()   { printf '\033[1;31m✗ %s\033[0m\n'  "$*" >&2; }

# wybór sumatora SHA-256 (Linux: sha256sum, macOS: shasum -a 256)
if command -v sha256sum >/dev/null 2>&1; then
    SHA="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    SHA="shasum -a 256"
else
    c_err "Brak sha256sum/shasum — nie da się zbudować MANIFEST."; exit 1
fi

# ── tryb VERIFY ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--verify" ]]; then
    DIR="${2:?Podaj katalog: --verify DIR}"
    cd "$DIR"
    [[ -f 00-MANIFEST.sha256 ]] || { c_err "Brak 00-MANIFEST.sha256 w $DIR"; exit 1; }
    c_info "Weryfikacja $DIR względem 00-MANIFEST.sha256 ..."
    if $SHA --check --quiet --strict 00-MANIFEST.sha256; then
        c_ok "Integralność OK — wszystkie pliki zgodne z manifestem."
        exit 0
    else
        c_err "NIEZGODNOŚĆ — archiwum uszkodzone lub zmodyfikowane!"; exit 1
    fi
fi

# ── parsowanie flag/argów ────────────────────────────────────────────────────
NO_DOCKER="${BPP_NO_DOCKER:-}"
NO_TARBALL="${BPP_NO_TARBALL:-}"
OUT_ARG=""
for arg in "$@"; do
    case "$arg" in
        --no-docker) NO_DOCKER=1 ;;
        --no-tar|--no-tarball) NO_TARBALL=1 ;;
        --*) c_err "Nieznana flaga: $arg"; exit 1 ;;
        *)   OUT_ARG="$arg" ;;
    esac
done

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${OUT_ARG:-$REPO_ROOT/../bpp-doomsday-$STAMP}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"                  # absolutna ścieżka
LOG="$OUT/00-build.log"

c_info "Cel archiwum: $OUT"
c_info "Python target dla wheeli linux: $PYVER ($PYTAG)"
echo "build started: $STAMP" >"$LOG"

# pip wołany przez uv (uv dostarcza pip do venv on-demand: --with pip)
pipdl() { uv run --with pip -- python -m pip download "$@"; }

# ═════════════════════════════════════════════════════════════════════════════
# WARSTWA 1 — kod aplikacji BPP + "przepisy" (lockfile'e)
# ═════════════════════════════════════════════════════════════════════════════
c_info "[1/5] Kod BPP (git bundle) + lockfile'e (przepisy) ..."
mkdir -p "$OUT/01-app"
git bundle create "$OUT/01-app/bpp.bundle" --all
# kopie "przepisów" — dzięki nim future-you zweryfikuje pobrane bajty
cp uv.lock yarn.lock package.json pyproject.toml "$OUT/01-app/"
# pełny, zamrożony eksport zależności Pythona (z markerami i git-depem)
uv export --frozen --no-hashes --no-emit-project --all-extras \
    -o "$OUT/01-app/requirements.export.txt" 2>>"$LOG" \
    || uv export --frozen --no-hashes --no-emit-project \
        -o "$OUT/01-app/requirements.export.txt" 2>>"$LOG"
# wariant bez git-depa (do passów wheelowych — fork nie ma wheela)
grep -v 'git+' "$OUT/01-app/requirements.export.txt" \
    >"$OUT/01-app/requirements.nogit.txt" || true
# czysta lista name==version (markery wycięte) do per-paczkowych pętli wheel
sed -E 's/ ;.*//; /@ /d; /^[[:space:]]*#/d; /^[[:space:]]*$/d' \
    "$OUT/01-app/requirements.export.txt" \
    | sed -E 's/[[:space:]]+$//' >"$OUT/01-app/requirements.pins.txt" || true
c_ok "Warstwa 1 gotowa ($(wc -l <"$OUT/01-app/requirements.pins.txt") pinned pkgs)."

# ═════════════════════════════════════════════════════════════════════════════
# WARSTWA 2 — źródła Python: sdist (krytyczne) + wheels host/linux (redundancja)
# ═════════════════════════════════════════════════════════════════════════════
c_info "[2/5] Źródła Python ..."
mkdir -p "$OUT/02-python/sdist" "$OUT/02-python/wheels-host" \
         "$OUT/02-python/wheels-linux"
PYLOG="$OUT/02-python/download.log"
: >"$PYLOG"

# 2a. sdist — DOOMSDAY-KRYTYCZNE: prawdziwe źródła, platform-independent.
#     Zawiera też git-fork (pip sklonuje @sha i zbuduje z niego sdist).
c_info "    2a. sdist (źródła, --no-binary) — to jest core archiwum ..."
if pipdl -r "$OUT/01-app/requirements.export.txt" \
        --no-binary=:all: --no-deps \
        -d "$OUT/02-python/sdist" >>"$PYLOG" 2>&1; then
    c_ok "    sdist: $(ls "$OUT/02-python/sdist" | wc -l | tr -d ' ') archiwów."
else
    c_warn "    sdist: część paczek nie miała sdista (patrz download.log)."
    c_warn "    To jedyna warstwa ze ŹRÓDŁAMI Python — sprawdź log uważnie!"
fi

# 2b. wheels-host — gotowe binarki pod TĘ maszynę (szybkie offline install).
#     Per-paczka, best-effort: jedna porażka nie zabija reszty.
c_info "    2b. wheels-host (binarki pod bieżącą platformę) ..."
while IFS= read -r pkg; do
    [[ -z "$pkg" ]] && continue
    pipdl "$pkg" --only-binary=:all: --no-deps \
        -d "$OUT/02-python/wheels-host" >>"$PYLOG" 2>&1 \
        || echo "host-miss: $pkg" >>"$PYLOG"
done <"$OUT/01-app/requirements.pins.txt"
c_ok "    wheels-host: $(ls "$OUT/02-python/wheels-host" | wc -l | tr -d ' ') wheeli."

# 2c. wheels-linux — binarki pod produkcję (manylinux x86_64, Python $PYVER).
#     Best-effort: nie każda paczka ma manylinux wheel; częściowo = OK.
c_info "    2c. wheels-linux (manylinux x86_64, py$PYVER) ..."
while IFS= read -r pkg; do
    [[ -z "$pkg" ]] && continue
    pipdl "$pkg" --only-binary=:all: --no-deps \
        --implementation cp --python-version "${PYVER//./}" --abi "$PYTAG" \
        --platform manylinux2014_x86_64 \
        --platform manylinux_2_17_x86_64 \
        --platform manylinux_2_28_x86_64 \
        -d "$OUT/02-python/wheels-linux" >>"$PYLOG" 2>&1 \
        || echo "linux-miss: $pkg" >>"$PYLOG"
done <"$OUT/01-app/requirements.pins.txt"
c_ok "    wheels-linux: $(ls "$OUT/02-python/wheels-linux" | wc -l | tr -d ' ') wheeli."
c_ok "Warstwa 2 gotowa."

# ═════════════════════════════════════════════════════════════════════════════
# WARSTWA 3 — źródła JavaScript: yarn v1 offline mirror (.tgz każdej paczki)
# ═════════════════════════════════════════════════════════════════════════════
c_info "[3/5] Źródła JavaScript (yarn offline mirror) ..."
mkdir -p "$OUT/03-js/npm-mirror"
if command -v yarn >/dev/null 2>&1; then
    # Izolacja: nadpisujemy HOME → yarn pisze .yarnrc do tmp (globalny ~/.yarnrc
    # NIETKNIĘTY), a install leci w tmp-kopii (repo node_modules NIETKNIĘTE).
    JS_TMP="$(mktemp -d)"
    trap 'rm -rf "$JS_TMP"' EXIT
    cp package.json yarn.lock "$JS_TMP/"
    (
        cd "$JS_TMP"
        export HOME="$JS_TMP"
        yarn config set yarn-offline-mirror "$OUT/03-js/npm-mirror" >/dev/null
        yarn config set yarn-offline-mirror-pruning false >/dev/null
        # --frozen-lockfile: nie ruszaj yarn.lock; --ignore-scripts: bezpiecznie
        yarn install --frozen-lockfile --ignore-scripts --non-interactive \
            >>"$LOG" 2>&1
    ) && c_ok "    npm-mirror: $(ls "$OUT/03-js/npm-mirror"/*.tgz 2>/dev/null \
            | wc -l | tr -d ' ') tarballi." \
      || c_warn "    yarn install częściowo zawiódł (patrz 00-build.log)."
    rm -rf "$JS_TMP"; trap - EXIT
else
    c_warn "    Brak 'yarn' w PATH — pomijam mirror JS (zainstaluj yarn v1)."
fi
c_ok "Warstwa 3 gotowa."

# ═════════════════════════════════════════════════════════════════════════════
# WARSTWA 4 — forki git (NAJBARDZIEJ KRUCHE: prywatne konto, brak rejestru)
# ═════════════════════════════════════════════════════════════════════════════
c_info "[4/5] Forki git (mirror clone — pełna historia) ..."
mkdir -p "$OUT/04-git-forks"
mirror_clone() {
    local url="$1" name="$2"
    local dst="$OUT/04-git-forks/$name"
    rm -rf "$dst"
    if git clone --mirror "$url" "$dst" >>"$LOG" 2>&1; then
        c_ok "    $name (mirror)."
    else
        c_warn "    Nie udało się sklonować $url — JUŻ NIEDOSTĘPNY?!"
    fi
}
mirror_clone "https://github.com/mpasternak/django-import-export.git" \
             "django-import-export.git"
mirror_clone "https://github.com/mpasternak/select2-foundation.git" \
             "select2-foundation.git"
c_ok "Warstwa 4 gotowa."

# ═════════════════════════════════════════════════════════════════════════════
# WARSTWA 5 — obrazy Docker (docker save) — best-effort, opcjonalne
# ═════════════════════════════════════════════════════════════════════════════
if [[ -n "$NO_DOCKER" ]]; then
    c_info "[5/5] Warstwa Docker pominięta (--no-docker)."
elif ! command -v docker >/dev/null 2>&1; then
    c_warn "[5/5] Brak 'docker' w PATH — pomijam warstwę systemową."
else
    c_info "[5/5] Obrazy Docker (docker save | zstd) ..."
    mkdir -p "$OUT/05-docker"
    for img in $IMAGES; do
        safe="${img//[\/:]/_}"
        out_tar="$OUT/05-docker/${safe}.tar.zst"
        if ! docker image inspect "$img" >/dev/null 2>&1; then
            c_info "    pull $img ..."
            docker pull "$img" >>"$LOG" 2>&1 \
                || { c_warn "    Nie ma lokalnie ani w rejestrze: $img"; continue; }
        fi
        if docker save "$img" | zstd -q -19 -T0 -o "$out_tar"; then
            c_ok "    $img → $(basename "$out_tar") \
($(du -h "$out_tar" | cut -f1))."
        else
            c_warn "    docker save $img zawiódł."
        fi
    done
fi

# ═════════════════════════════════════════════════════════════════════════════
# README + MANIFEST.sha256 (kryptograficzny snapshot integralności)
# ═════════════════════════════════════════════════════════════════════════════
c_info "Generuję README + MANIFEST.sha256 ..."
cat >"$OUT/00-README.txt" <<EOF
BPP — DOOMSDAY ARCHIVE
Zbudowano: $STAMP
Repo HEAD: $(git rev-parse HEAD)
Branch:    $(git rev-parse --abbrev-ref HEAD)

ZAWARTOŚĆ
  01-app/          kod BPP (bpp.bundle) + lockfile'e (przepisy)
  02-python/       sdist (źródła) + wheels-host + wheels-linux
  03-js/           yarn offline mirror (.tgz)
  04-git-forks/    mirror-clone'y forków (NAJBARDZIEJ KRUCHE źródła)
  05-docker/       docker save obrazów (jeśli budowane)
  00-MANIFEST.sha256   sumy kontrolne wszystkich plików
  00-build.log / 02-python/download.log   logi (co się udało/nie udało)

WERYFIKACJA INTEGRALNOŚCI
  bin/make-doomsday-archive.sh --verify "$OUT"

ODTWORZENIE — Python (offline, ze źródeł lub wheeli):
  uv venv && source .venv/bin/activate
  pip install --no-index \\
      --find-links 02-python/wheels-linux \\
      --find-links 02-python/wheels-host \\
      --find-links 02-python/sdist \\
      -r 01-app/requirements.nogit.txt
  # git-fork django-import-export odtwórz z 04-git-forks/ (patrz niżej)

ODTWORZENIE — JavaScript (offline):
  yarn config set yarn-offline-mirror "\$PWD/03-js/npm-mirror"
  yarn install --offline --frozen-lockfile

ODTWORZENIE — forki git:
  git clone 04-git-forks/django-import-export.git <gdziekolwiek>
  git clone 04-git-forks/select2-foundation.git   <gdziekolwiek>
  (mają pełną historię; checkout pinned SHA z lockfile'i)

ODTWORZENIE — obrazy Docker:
  zstd -dc 05-docker/<obraz>.tar.zst | docker load
EOF

# MANIFEST: sumy WSZYSTKICH plików poza samym manifestem.
( cd "$OUT"
  find . -type f ! -name '00-MANIFEST.sha256' -print0 \
      | sort -z \
      | xargs -0 $SHA >"00-MANIFEST.sha256"
)
N_FILES="$(wc -l <"$OUT/00-MANIFEST.sha256" | tr -d ' ')"
c_ok "MANIFEST.sha256: $N_FILES plików."

# ── opcjonalne spakowanie całości ────────────────────────────────────────────
if [[ -z "$NO_TARBALL" ]]; then
    c_info "Pakuję całość w .tar.zst ..."
    TARBALL="$OUT.tar.zst"
    ( cd "$(dirname "$OUT")" && tar -cf - "$(basename "$OUT")" \
        | zstd -q -19 -T0 -o "$TARBALL" )
    c_ok "Tarball: $TARBALL ($(du -h "$TARBALL" | cut -f1))"
fi

echo
c_ok "GOTOWE. Rozmiar archiwum: $(du -sh "$OUT" | cut -f1)"
c_info "Katalog: $OUT"
c_info "Weryfikacja: bin/make-doomsday-archive.sh --verify \"$OUT\""
