#!/bin/bash
set -euo pipefail

# bin/review-branches.sh
#
# Przegląd wszystkich gałęzi (lokalnych i zdalnych) z informacją o:
#  - bieżącej gałęzi
#  - upstream + ahead/behind względem upstreamu
#  - ahead/behind względem gałęzi bazowej (domyślnie 'dev')
#  - statusie merge do bazowej
#  - przypisanym worktree
#  - dacie i temacie ostatniego commitu
#
# Wyrównuje kolumny ręcznie (bo `column -t` nie radzi sobie z ANSI).

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
GREY=$'\033[0;90m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
NC=$'\033[0m'

NO_FETCH=false
NO_COLOR=false
NO_PR=false
COMPARE_BRANCH=""

usage() {
    cat <<EOF
${BOLD}Przegląd gałęzi BPP${NC}

Pokazuje lokalne i zdalne gałęzie z informacją o tracking-u, ahead/behind,
statusie merge do bazowej (domyślnie 'dev'), worktree i ostatnim commicie.

${YELLOW}Użycie:${NC}
    $(basename "$0") [opcje]

${YELLOW}Opcje:${NC}
    --no-fetch       Pomiń 'git fetch --all --prune'
    --no-color       Wyłącz kolorowanie
    --no-pr          Pomiń pobieranie listy otwartych PR-ów (gh pr list)
    --base <branch>  Inna gałąź bazowa zamiast 'dev'
    -h, --help       Pokaż tę pomoc

${YELLOW}Legenda:${NC}
    ↑N   ahead o N commitów
    ↓N   behind o N commitów
    =    równo
    WT   ma podpięty worktree
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-fetch)  NO_FETCH=true; shift ;;
        --no-color)  NO_COLOR=true; shift ;;
        --no-pr)     NO_PR=true; shift ;;
        --base)      COMPARE_BRANCH="${2:-}"; shift 2 ;;
        -h|--help)   usage; exit 0 ;;
        *) echo "Nieznana opcja: $1" >&2; usage; exit 2 ;;
    esac
done

if $NO_COLOR; then
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""; GREY=""
    BOLD=""; DIM=""; NC=""
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "${RED}Nie jestem w repozytorium git.${NC}" >&2
    exit 3
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ -z "$COMPARE_BRANCH" ]]; then
    for cand in dev main master; do
        if git show-ref --verify --quiet "refs/heads/$cand"; then
            COMPARE_BRANCH="$cand"
            break
        fi
    done
fi
if [[ -z "$COMPARE_BRANCH" ]] || \
   ! git show-ref --verify --quiet "refs/heads/$COMPARE_BRANCH"; then
    echo "${RED}Brak lokalnej gałęzi bazowej '${COMPARE_BRANCH:-?}'${NC}" >&2
    exit 4
fi
REMOTE_BASE="origin/$COMPARE_BRANCH"

if ! $NO_FETCH; then
    echo "${DIM}Fetch + prune...${NC}" >&2
    if ! git fetch --all --prune --quiet 2>/dev/null; then
        echo "${YELLOW}Ostrzeżenie: fetch nie powiódł się — dane mogą być nieaktualne.${NC}" >&2
    fi
fi

CURRENT="$(git rev-parse --abbrev-ref HEAD)"

# ---------- Worktree mapping (branch -> path) ----------
WT_BRANCHES=()
WT_PATHS=()
_wt_path=""
while IFS= read -r line; do
    case "$line" in
        worktree\ *)  _wt_path="${line#worktree }" ;;
        branch\ *)    WT_BRANCHES+=("${line#branch refs/heads/}")
                      WT_PATHS+=("$_wt_path") ;;
    esac
done < <(git worktree list --porcelain)

worktree_for() {
    local b="$1" i
    for i in "${!WT_BRANCHES[@]}"; do
        if [[ "${WT_BRANCHES[$i]}" == "$b" ]]; then
            printf '%s' "${WT_PATHS[$i]}"
            return
        fi
    done
}

# ---------- Open PR mapping (branch -> #num + url) ----------
PR_BRANCHES=()
PR_NUMBERS=()
PR_URLS=()
if ! $NO_PR && command -v gh >/dev/null 2>&1; then
    while IFS=$'\t' read -r _num _branch _url; do
        [[ -z "$_branch" ]] && continue
        PR_BRANCHES+=("$_branch")
        PR_NUMBERS+=("$_num")
        PR_URLS+=("$_url")
    done < <(gh pr list --state open --limit 200 \
                 --json number,headRefName,url \
                 --jq '.[] | [.number, .headRefName, .url] | @tsv' \
                 2>/dev/null || true)
fi

pr_for() {
    # Echo a styled "#NUM" cell (OSC 8 hyperlink) for branch $1, or empty.
    local b="$1" i
    for i in "${!PR_BRANCHES[@]}"; do
        if [[ "${PR_BRANCHES[$i]}" == "$b" ]]; then
            local linked
            linked=$(hyperlink "${PR_URLS[$i]}" "#${PR_NUMBERS[$i]}")
            printf '%s%s%s' "$CYAN" "$linked" "$NC"
            return
        fi
    done
}

# ---------- Helpers ----------
strip_ansi() {
    # Bash 3.2 compatible: feed via stdin, sed strips CSI (\e[...m) and
    # OSC 8 hyperlink (\e]8;;URL\e\\TEXT\e]8;;\e\\) sequences.
    printf '%s' "$1" \
        | sed -E $'s/\033\\[[0-9;]*m//g; s/\033]8;;[^\033]*\033\\\\//g'
}

hyperlink() {
    # OSC 8 clickable link. Args: url, text. Falls back to plain URL when
    # --no-color is set (some renderers also strip OSC 8 then).
    local url="$1" text="$2"
    if $NO_COLOR; then
        printf '%s' "$url"
    else
        printf '\033]8;;%s\033\\%s\033]8;;\033\\' "$url" "$text"
    fi
}

# Visible width of a string (after stripping ANSI). Counts characters, not bytes.
# `wc -m` z UTF-8 locale liczy znaki, nie bajty — kluczowe dla ↑↓ (3 bajty/znak).
visible_width() {
    local plain n
    plain=$(strip_ansi "$1")
    n=$(printf '%s' "$plain" | LC_ALL="${LANG:-en_US.UTF-8}" wc -m)
    # wc dopisuje spacje przed liczbą; usuń.
    printf '%s' "${n// /}"
}

pad_right() {
    local val="$1" width="$2" w
    w=$(visible_width "$val")
    local pad=$(( width - w ))
    (( pad < 0 )) && pad=0
    printf '%s%*s' "$val" "$pad" ''
}

ab_styled() {
    # ahead/behind mini-formatter. Args: ahead, behind.
    local a="$1" b="$2"
    if [[ "$a" == "0" && "$b" == "0" ]]; then
        printf '%s=%s' "$GREY" "$NC"
        return
    fi
    local out=""
    [[ "$a" != "0" && "$a" != "" ]] && out="${YELLOW}↑${a}${NC}"
    if [[ "$a" != "0" && "$a" != "" && "$b" != "0" && "$b" != "" ]]; then
        out+=" "
    fi
    [[ "$b" != "0" && "$b" != "" ]] && out+="${RED}↓${b}${NC}"
    printf '%s' "$out"
}

ab_vs() {
    # ahead/behind of $1 vs $2 (both must be valid refs).
    local from="$1" to="$2" a b
    a=$(git rev-list --count "$to..$from" 2>/dev/null || echo "?")
    b=$(git rev-list --count "$from..$to" 2>/dev/null || echo "?")
    ab_styled "$a" "$b"
}

truncate_str() {
    # Truncate to max $2 chars (visible). Plain only — used on raw strings.
    local s="$1" max="$2"
    if (( ${#s} > max )); then
        printf '%s...' "${s:0:$((max-3))}"
    else
        printf '%s' "$s"
    fi
}

section() {
    printf '\n%s%s=== %s ===%s\n' "$BOLD" "$BLUE" "$1" "$NC"
}

repeat_char() {
    local char="$1" n="$2" i
    for ((i=0; i<n; i++)); do
        printf '%s' "$char"
    done
}

hline() {
    # Box-drawing horizontal line. Args: left mid right widths...
    # Każda komórka rezerwuje (width + 2) znaków (po jednym znaku marginesu).
    local left="$1" mid="$2" right="$3"
    shift 3
    printf '%s%s' "$DIM" "$left"
    local first=true w
    for w in "$@"; do
        if $first; then
            first=false
        else
            printf '%s' "$mid"
        fi
        repeat_char '─' "$((w + 2))"
    done
    printf '%s%s\n' "$right" "$NC"
}

box_top() { hline '┌' '┬' '┐' "$@"; }
box_mid() { hline '├' '┼' '┤' "$@"; }
box_bot() { hline '└' '┴' '┘' "$@"; }

# ---------- Local branches ----------
MERGED_LOCAL=$(git for-each-ref --merged "$COMPARE_BRANCH" \
                 --format='%(refname:short)' refs/heads/)

is_merged_local() {
    grep -Fxq "$1" <<<"$MERGED_LOCAL"
}

L_C1=(); L_C2=(); L_C3=(); L_C4=(); L_C5=(); L_C6=(); L_C7=(); L_C8=(); L_C9=()

while IFS='|' read -r branch upstream track; do
    [[ -z "$branch" ]] && continue

    if [[ "$branch" == "$CURRENT" ]]; then
        c1="${GREEN}*${NC}"
        c2="${GREEN}${BOLD}${branch}${NC}"
    else
        c1=" "
        c2="$branch"
    fi

    if [[ -z "$upstream" ]]; then
        c3="${GREY}(brak upstream)${NC}"
    elif [[ "$track" == *"gone"* ]]; then
        c3="${RED}${upstream} [gone]${NC}"
    else
        c3="$upstream"
    fi

    # vs upstream — z `track` zamiast oddzielnego rev-list
    if [[ -z "$upstream" ]]; then
        c4="${GREY}—${NC}"
    elif [[ "$track" == *"gone"* ]]; then
        c4="${RED}gone${NC}"
    else
        a=0; b=0
        if [[ "$track" =~ ahead\ ([0-9]+) ]]; then a="${BASH_REMATCH[1]}"; fi
        if [[ "$track" =~ behind\ ([0-9]+) ]]; then b="${BASH_REMATCH[1]}"; fi
        c4=$(ab_styled "$a" "$b")
    fi

    if [[ "$branch" == "$COMPARE_BRANCH" ]]; then
        c5="${GREY}(baza)${NC}"
        c6="${GREY}—${NC}"
    else
        c5=$(ab_vs "$branch" "$COMPARE_BRANCH")
        if is_merged_local "$branch"; then
            c6="${GREEN}✓ tak${NC}"
        else
            c6="${YELLOW}✗ nie${NC}"
        fi
    fi

    wt=$(worktree_for "$branch")
    if [[ -n "$wt" ]]; then
        c7="${CYAN}WT${NC}"
    else
        c7=""
    fi

    c8=$(pr_for "$branch")

    last=$(git log -1 --format='%ad %s' --date=short "$branch" 2>/dev/null || echo "")
    last=$(truncate_str "$last" 60)
    c9="${DIM}${last}${NC}"

    L_C1+=("$c1"); L_C2+=("$c2"); L_C3+=("$c3"); L_C4+=("$c4")
    L_C5+=("$c5"); L_C6+=("$c6"); L_C7+=("$c7"); L_C8+=("$c8"); L_C9+=("$c9")
done < <(git for-each-ref \
            --format='%(refname:short)|%(upstream:short)|%(upstream:track)' \
            refs/heads/ | sort)

# Headers
H1=" "
H2="branch"
H3="upstream"
H4="vs upstream"
H5="vs ${COMPARE_BRANCH}"
H6="merged → ${COMPARE_BRANCH}"
H7="wt"
H8="PR"
H9="last commit"

# Width = max of header and all column values.
maxw_of() {
    local hdr="$1"; shift
    local m
    m=$(visible_width "$hdr")
    local v vw
    for v in "$@"; do
        vw=$(visible_width "$v")
        (( vw > m )) && m=$vw
    done
    printf '%s' "$m"
}

W1=$(maxw_of "$H1" "${L_C1[@]:-}")
W2=$(maxw_of "$H2" "${L_C2[@]:-}")
W3=$(maxw_of "$H3" "${L_C3[@]:-}")
W4=$(maxw_of "$H4" "${L_C4[@]:-}")
W5=$(maxw_of "$H5" "${L_C5[@]:-}")
W6=$(maxw_of "$H6" "${L_C6[@]:-}")
W7=$(maxw_of "$H7" "${L_C7[@]:-}")
W8=$(maxw_of "$H8" "${L_C8[@]:-}")
W9=$(maxw_of "$H9" "${L_C9[@]:-}")

print_local_row() {
    printf '%s│%s ' "$DIM" "$NC"
    pad_right "$1" "$W1"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$2" "$W2"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$3" "$W3"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$4" "$W4"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$5" "$W5"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$6" "$W6"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$7" "$W7"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$8" "$W8"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$9" "$W9"; printf ' %s│%s\n' "$DIM" "$NC"
}

section "Lokalne gałęzie (baza: ${COMPARE_BRANCH})"
box_top "$W1" "$W2" "$W3" "$W4" "$W5" "$W6" "$W7" "$W8" "$W9"
print_local_row \
    "${BOLD}$H1${NC}" "${BOLD}$H2${NC}" "${BOLD}$H3${NC}" "${BOLD}$H4${NC}" \
    "${BOLD}$H5${NC}" "${BOLD}$H6${NC}" "${BOLD}$H7${NC}" "${BOLD}$H8${NC}" \
    "${BOLD}$H9${NC}"
box_mid "$W1" "$W2" "$W3" "$W4" "$W5" "$W6" "$W7" "$W8" "$W9"
for i in "${!L_C2[@]}"; do
    print_local_row \
        "${L_C1[$i]}" "${L_C2[$i]}" "${L_C3[$i]}" "${L_C4[$i]}" \
        "${L_C5[$i]}" "${L_C6[$i]}" "${L_C7[$i]}" "${L_C8[$i]}" \
        "${L_C9[$i]}"
done
box_bot "$W1" "$W2" "$W3" "$W4" "$W5" "$W6" "$W7" "$W8" "$W9"

# ---------- Worktrees legend ----------
if (( ${#WT_BRANCHES[@]} > 0 )); then
    section "Worktrees"
    # Wide enough column for branch name.
    WTBW=0
    for b in "${WT_BRANCHES[@]}"; do
        (( ${#b} > WTBW )) && WTBW=${#b}
    done
    for i in "${!WT_BRANCHES[@]}"; do
        pad_right "${CYAN}${WT_BRANCHES[$i]}${NC}" "$WTBW"
        printf '  %s%s%s\n' "$DIM" "${WT_PATHS[$i]}" "$NC"
    done
fi

# ---------- Remote branches ----------
if ! git show-ref --verify --quiet "refs/remotes/${REMOTE_BASE}"; then
    echo
    echo "${YELLOW}Brak ${REMOTE_BASE} — pomijam sekcję zdalnych.${NC}"
    exit 0
fi

MERGED_REMOTE=$(git for-each-ref --merged "$REMOTE_BASE" \
                  --format='%(refname:short)' refs/remotes/origin/)

is_merged_remote() {
    grep -Fxq "$1" <<<"$MERGED_REMOTE"
}

R_C1=(); R_C2=(); R_C3=(); R_C4=(); R_C5=()

while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    [[ "$ref" == "origin/HEAD" ]] && continue
    [[ "$ref" == "$REMOTE_BASE" ]] && continue
    # `refs/remotes/origin/HEAD` skraca się do samej nazwy zdalnego ("origin")
    # — pomijamy, bo to alias na origin/dev.
    [[ "$ref" != */* ]] && continue

    if is_merged_remote "$ref"; then
        m="${GREEN}✓ tak${NC}"
    else
        m="${YELLOW}✗ nie${NC}"
    fi

    ab=$(ab_vs "$ref" "$REMOTE_BASE")

    pr_cell=$(pr_for "${ref#origin/}")

    last=$(git log -1 --format='%ad %s' --date=short "$ref" 2>/dev/null || echo "")
    last=$(truncate_str "$last" 60)
    last_styled="${DIM}${last}${NC}"

    R_C1+=("$ref"); R_C2+=("$ab"); R_C3+=("$m")
    R_C4+=("$pr_cell"); R_C5+=("$last_styled")
done < <(git for-each-ref --format='%(refname:short)' refs/remotes/origin/ | sort)

RH1="branch"
RH2="vs ${REMOTE_BASE}"
RH3="merged → ${REMOTE_BASE}"
RH4="PR"
RH5="last commit"

RW1=$(maxw_of "$RH1" "${R_C1[@]:-}")
RW2=$(maxw_of "$RH2" "${R_C2[@]:-}")
RW3=$(maxw_of "$RH3" "${R_C3[@]:-}")
RW4=$(maxw_of "$RH4" "${R_C4[@]:-}")
RW5=$(maxw_of "$RH5" "${R_C5[@]:-}")

print_remote_row() {
    printf '%s│%s ' "$DIM" "$NC"
    pad_right "$1" "$RW1"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$2" "$RW2"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$3" "$RW3"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$4" "$RW4"; printf ' %s│%s ' "$DIM" "$NC"
    pad_right "$5" "$RW5"; printf ' %s│%s\n' "$DIM" "$NC"
}

section "Zdalne gałęzie (origin/*, baza: ${REMOTE_BASE})"
box_top "$RW1" "$RW2" "$RW3" "$RW4" "$RW5"
print_remote_row \
    "${BOLD}$RH1${NC}" "${BOLD}$RH2${NC}" "${BOLD}$RH3${NC}" \
    "${BOLD}$RH4${NC}" "${BOLD}$RH5${NC}"
box_mid "$RW1" "$RW2" "$RW3" "$RW4" "$RW5"
for i in "${!R_C1[@]}"; do
    print_remote_row "${R_C1[$i]}" "${R_C2[$i]}" "${R_C3[$i]}" \
        "${R_C4[$i]}" "${R_C5[$i]}"
done
box_bot "$RW1" "$RW2" "$RW3" "$RW4" "$RW5"

echo
echo "${DIM}Tip: --no-fetch (szybciej), --base <branch> (inna baza), --no-color, --no-pr.${NC}"
