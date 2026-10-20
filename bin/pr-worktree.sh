#!/usr/bin/env bash
#
# Testowanie pull requestów z GitHuba w osobnym worktree.
#
# Każdy PR dostaje własny worktree `<katalog nadrzędny repo>/bpp-pr-<N>`
# (siostra głównego checkoutu, np. ~/Programowanie/bpp-pr-856) z własnym
# `.venv` i `node_modules` — testowanie PR-a nie rusza bieżącej gałęzi ani
# niezacommitowanej pracy w głównym checkoucie. Dev stack startuje przez
# `run-site` na losowych portach i świeżych testcontainers, więc baza po
# migracjach z PR-a nie przecieka do innych PR-ów ani do głównego stacka.
#
# Wywoływane przez targety Makefile:
#   make pr PR=856                  # pobierz/odśwież PR i uruchom run-site
#   make pr PR=856 NO_RUN=1         # tylko przygotuj worktree
#   make pr PR=856 DUMP=uafm        # run-site na najnowszym backupie hosta
#   make pr PR=856 DUMP=plik.sql.gz # ... albo na konkretnym pliku dumpa
#   make pr PR=856 ARGS="--no-celery --no-browser"
#   make pr-list                    # lokalne worktree PR-ów + otwarte PR-y
#   make pr-clean PR=856            # usuń worktree i gałąź pr-856
#
# Zmienne środowiskowe:
#   BPP_PR_DUMP      domyślny DUMP, gdy nie podano (DUMP=none = goła baza)
#   BPP_BACKUPS_DIR  gdzie szukać backupów hostów (domyślnie ~/Backups)
#   BPP_PR_BASE_DIR  katalog, w którym powstają worktree

set -euo pipefail

usage() {
    cat <<'EOF'
Użycie:
  bin/pr-worktree.sh start <PR> [--dump PLIK|HOST|none] [--no-run] [-- ARGUMENTY-RUN-SITE]
  bin/pr-worktree.sh list
  bin/pr-worktree.sh clean <PR> [--force]

start  Pobiera głowę PR-a (refs/pull/<PR>/head — działa też dla forków),
       tworzy worktree bpp-pr-<PR> (albo resetuje istniejący do najnowszego
       commita PR-a), synchronizuje .venv i uruchamia `uv run run-site run`.
       --dump HOST bierze najnowszy db-backup-* z ~/Backups/*HOST*/;
       bez --dump używany jest $BPP_PR_DUMP (jeśli ustawiony).
list   Pokazuje lokalne worktree bpp-pr-*, dostępne backupy hostów oraz
       otwarte PR-y na GitHubie.
clean  Usuwa worktree bpp-pr-<PR> i lokalną gałąź pr-<PR>. Odmawia, gdy
       worktree ma lokalne zmiany albo działa w nim run-site (--force
       pomija oba sprawdzenia).
EOF
}

die() {
    echo "BŁĄD: $*" >&2
    exit 1
}

# Główny checkout = katalog nad wspólnym .git. Działa także wywołane
# z wnętrza innego worktree.
GIT_COMMON_DIR=$(git rev-parse --path-format=absolute --git-common-dir)
MAIN=$(dirname "$GIT_COMMON_DIR")
BASE_DIR="${BPP_PR_BASE_DIR:-$(dirname "$MAIN")}"

require_pr_number() {
    [[ "${1:-}" =~ ^[0-9]+$ ]] || die "numer PR-a musi być liczbą (dostałem: '${1:-}')"
}

worktree_path() {
    echo "$BASE_DIR/bpp-pr-$1"
}

# Zmiany w plikach śledzonych + nieśledzone nieignorowane. Pliki z
# .gitignore (.venv, node_modules, .dev_helpers_*) się nie liczą.
is_dirty() {
    [[ -n "$(git -C "$1" status --porcelain)" ]]
}

BACKUPS_DIR="${BPP_BACKUPS_DIR:-$HOME/Backups}"
DUMP_PATTERN='^db-backup.*\.(tar\.gz|tgz|pg_dump|pgdump|dump|sql|sql\.gz)$'

newest_backup_in() {
    # shellcheck disable=SC2010  # nazwy backupów nie mają spacji/nowych linii
    ls -t "$1" 2>/dev/null | grep -E "$DUMP_PATTERN" | head -1
}

# Katalogi hostów w $BACKUPS_DIR, które mają choć jeden backup bazy.
backup_host_dirs() {
    local d
    for d in "$BACKUPS_DIR"/*/; do
        d=${d%/}
        [[ -n "$(newest_backup_in "$d")" ]] && echo "$d"
    done
}

# DUMP to ścieżka do pliku albo fragment nazwy hosta z $BACKUPS_DIR
# (np. "uafm" -> najnowszy db-backup-* z ~/Backups/bpp.uafm.edu.pl/).
resolve_dump() {
    local spec=$1
    if [[ -e "$spec" ]]; then
        echo "$(cd "$(dirname "$spec")" && pwd)/$(basename "$spec")"
        return
    fi
    [[ -d "$BACKUPS_DIR" ]] || die "nie ma pliku '$spec' ani katalogu $BACKUPS_DIR"
    local dirs=() d
    while read -r d; do
        # Dokładna nazwa katalogu wygrywa z dopasowaniem fragmentu.
        if [[ "$(basename "$d")" == "$spec" ]]; then dirs=("$d"); break; fi
        [[ "$(basename "$d")" == *"$spec"* ]] && dirs+=("$d")
    done < <(backup_host_dirs)
    case ${#dirs[@]} in
        0) die "nie ma pliku '$spec' ani backupu hosta pasującego do '$spec' w $BACKUPS_DIR (zobacz: make pr-list)" ;;
        1) echo "${dirs[0]}/$(newest_backup_in "${dirs[0]}")" ;;
        *) printf '  %s\n' "${dirs[@]}" >&2
           die "'$spec' pasuje do kilku hostów — podaj dokładniej" ;;
    esac
}

print_pr_info() {
    local pr=$1
    if ! command -v gh >/dev/null 2>&1; then
        echo "(brak gh CLI — pomijam tytuł i opis PR-a)"
        return
    fi
    if ! gh pr view "$pr" --repo iplweb/bpp \
        --json number,title,author,headRefName,baseRefName,state,url \
        --template '#{{.number}} {{.title}}
autor: {{.author.login}}   {{.headRefName}} -> {{.baseRefName}}   [{{.state}}]
{{.url}}
'; then
        echo "UWAGA: gh pr view $pr się nie udało (sieć/auth?) — kontynuuję bez opisu" >&2
    fi
}

# node_modules: klon z głównego checkoutu (APFS clonefile = kopia-przy-zapisie,
# bez zajmowania miejsca), o ile lockfile się nie zmienił. W przeciwnym razie
# zostawiamy pusty katalog — `make assets` (hook run-site) zrobi yarn install.
prepare_node_modules() {
    local wt=$1
    [[ -e "$wt/node_modules" ]] && return
    if [[ ! -d "$MAIN/node_modules" ]]; then
        echo "-> node_modules: brak w głównym checkoucie, zainstaluje je make assets"
        return
    fi
    if ! cmp -s "$MAIN/yarn.lock" "$wt/yarn.lock" \
        || ! cmp -s "$MAIN/package.json" "$wt/package.json"; then
        echo "-> node_modules: PR zmienia package.json/yarn.lock, zainstaluje je make assets"
        return
    fi
    if [[ "$(uname -s)" != "Darwin" ]]; then
        echo "-> node_modules: klonowanie tylko na macOS (APFS), zainstaluje je make assets"
        return
    fi
    echo "-> node_modules: klonuję z głównego checkoutu (cp -c, APFS)"
    if ! cp -cR "$MAIN/node_modules" "$wt/node_modules"; then
        echo "UWAGA: klonowanie node_modules nie wyszło, make assets zrobi yarn install" >&2
        rm -rf "$wt/node_modules"
    fi
}

cmd_start() {
    local pr=${1:-}
    require_pr_number "$pr"
    shift
    local dump="${BPP_PR_DUMP:-}" no_run=""
    local runsite_args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dump) dump=${2:?--dump wymaga ścieżki}; shift 2 ;;
            --no-run) no_run=1; shift ;;
            --) shift; runsite_args=("$@"); break ;;
            *) die "nieznana opcja: $1" ;;
        esac
    done
    [[ "$dump" == "none" ]] && dump=""
    if [[ -n "$dump" ]]; then
        dump=$(resolve_dump "$dump") || exit 1
        echo "Dump: $dump ($(du -h "$dump" | cut -f1), $(date -r "$dump" '+%Y-%m-%d'))"
    else
        echo "Dump: brak — goła baza z baseline (DUMP=uafm albo BPP_PR_DUMP, żeby mieć dane)"
    fi

    local wt branch sha base
    wt=$(worktree_path "$pr")
    branch="pr-$pr"

    print_pr_info "$pr"
    echo

    echo "-> git fetch origin pull/$pr/head"
    git -C "$MAIN" fetch --quiet origin "pull/$pr/head" \
        || die "nie udało się pobrać PR-a #$pr (czy istnieje?)"
    sha=$(git -C "$MAIN" rev-parse FETCH_HEAD)

    if [[ -d "$wt" ]]; then
        if is_dirty "$wt"; then
            git -C "$wt" status --short >&2
            die "$wt ma lokalne zmiany — zacommituj/odrzuć je albo make pr-clean PR=$pr FORCE=1"
        fi
        echo "-> worktree istnieje, reset do $(git -C "$MAIN" log -1 --format='%h %s' "$sha")"
        git -C "$wt" checkout --quiet -B "$branch" "$sha"
    else
        echo "-> git worktree add $wt ($branch @ ${sha:0:9})"
        git -C "$MAIN" worktree add --quiet -B "$branch" "$wt" "$sha"
    fi

    # Bazę PR-a bierzemy z dev (99% PR-ów); dla podsumowania zmian to wystarcza.
    git -C "$MAIN" fetch --quiet origin dev
    base=$(git -C "$MAIN" merge-base origin/dev "$sha")
    echo
    echo "Zmienione pliki względem dev ($(git -C "$MAIN" rev-list --count "$base..$sha") commit(ów)):"
    git -C "$MAIN" diff --stat=88 "$base" "$sha" | tail -n 25
    if git -C "$MAIN" diff --name-only "$base" "$sha" | grep -q '/migrations/'; then
        echo
        echo "UWAGA: PR zawiera migracje — run-site postawi świeżą bazę i je zastosuje."
    fi
    echo

    prepare_node_modules "$wt"

    echo "-> uv sync --frozen (własne .venv worktree)"
    (cd "$wt" && uv sync --frozen --quiet)

    if [[ -n "$no_run" ]]; then
        echo
        echo "Gotowe. Worktree: $wt"
        echo "Uruchomienie: cd $wt && uv run run-site run"
        return
    fi

    local cmd=(uv run --frozen run-site run)
    [[ -n "$dump" ]] && cmd+=(--from-dump "$dump")
    cmd+=(${runsite_args[@]+"${runsite_args[@]}"})
    echo "-> cd $wt && ${cmd[*]}"
    cd "$wt"
    exec "${cmd[@]}"
}

cmd_list() {
    echo "Lokalne worktree PR-ów:"
    local found="" path pr
    while read -r path; do
        [[ "$(basename "$path")" =~ ^bpp-pr-([0-9]+)$ ]] || continue
        pr=${BASH_REMATCH[1]}
        found=1
        local flags=""
        is_dirty "$path" && flags+=" [lokalne zmiany]"
        [[ -f "$path/.dev_helpers_port" ]] \
            && flags+=" [run-site: http://localhost:$(cat "$path/.dev_helpers_port")]"
        echo "  #$pr  $path  $(git -C "$path" log -1 --format='%h %cr')$flags"
    done < <(git -C "$MAIN" worktree list --porcelain | sed -n 's/^worktree //p')
    [[ -n "$found" ]] || echo "  (brak)"

    echo
    echo "Backupy do DUMP=<host> (najnowszy z $BACKUPS_DIR, domyślny: ${BPP_PR_DUMP:-brak}):"
    local d f
    while read -r d; do
        f="$d/$(newest_backup_in "$d")"
        printf '  %-28s %6s  %s  %s\n' "$(basename "$d")" "$(du -h "$f" | cut -f1)" \
            "$(date -r "$f" '+%Y-%m-%d')" "$(basename "$f")"
    done < <(backup_host_dirs)

    echo
    if command -v gh >/dev/null 2>&1; then
        echo "Otwarte PR-y w iplweb/bpp:"
        gh pr list --repo iplweb/bpp --limit 30 \
            || echo "UWAGA: gh pr list się nie udało (sieć/auth?)" >&2
    else
        echo "(brak gh CLI — nie pokażę otwartych PR-ów)"
    fi
}

cmd_clean() {
    local pr=${1:-}
    require_pr_number "$pr"
    local force=""
    [[ "${2:-}" == "--force" ]] && force=1
    local wt branch
    wt=$(worktree_path "$pr")
    branch="pr-$pr"

    if [[ -d "$wt" ]]; then
        if [[ -z "$force" ]]; then
            if [[ -f "$wt/.dev_helpers_port" ]]; then
                die "w $wt chyba działa run-site (jest .dev_helpers_port) — zatrzymaj go (Ctrl+C) albo FORCE=1"
            fi
            if is_dirty "$wt"; then
                git -C "$wt" status --short >&2
                die "$wt ma lokalne zmiany — nie usuwam (FORCE=1 usunie mimo to)"
            fi
        fi
        echo "-> git worktree remove $wt"
        git -C "$MAIN" worktree remove --force "$wt"
    else
        echo "-> nie ma $wt, pomijam worktree"
        git -C "$MAIN" worktree prune
    fi

    if git -C "$MAIN" show-ref --verify --quiet "refs/heads/$branch"; then
        echo "-> git branch -D $branch"
        git -C "$MAIN" branch --quiet -D "$branch"
    fi
}

case "${1:-}" in
    start) shift; cmd_start "$@" ;;
    list) shift; cmd_list "$@" ;;
    clean) shift; cmd_clean "$@" ;;
    -h|--help|help) usage ;;
    *) usage >&2; exit 2 ;;
esac
