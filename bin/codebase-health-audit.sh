#!/bin/bash
# bin/codebase-health-audit.sh
# Skrypt audytu jakości kodu dla projektu BPP
#
# Użycie:
#   ./bin/codebase-health-audit.sh              # Kolorowy terminal
#   ./bin/codebase-health-audit.sh --markdown   # Raport Markdown
#   ./bin/codebase-health-audit.sh --python-only
#   ./bin/codebase-health-audit.sh --templates-only
#   ./bin/codebase-health-audit.sh --scss-only

set -euo pipefail

# Znajdź katalog główny projektu (gdzie jest pyproject.toml)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"

# Domyślne wartości
MARKDOWN_MODE=false
PYTHON_ONLY=false
TEMPLATES_ONLY=false
SCSS_ONLY=false

# Progi
PYTHON_LINE_LIMIT=600
PYTHON_LINE_CRITICAL=850
SCSS_LINE_LIMIT=500
COMPLEXITY_THRESHOLD=10
COMPLEXITY_CRITICAL=20

# Liczniki (bez tablic asocjacyjnych dla kompatybilności z bash 3.x)
COUNT_CRITICAL=0
COUNT_HIGH=0
COUNT_MEDIUM=0
COUNT_LOW=0

# Kolory (wyłączone w trybie markdown)
setup_colors() {
    if [[ "$MARKDOWN_MODE" == "true" ]] || [[ ! -t 1 ]]; then
        RED=""
        YELLOW=""
        GREEN=""
        BLUE=""
        CYAN=""
        BOLD=""
        RESET=""
    else
        RED='\033[0;31m'
        YELLOW='\033[0;33m'
        GREEN='\033[0;32m'
        BLUE='\033[0;34m'
        CYAN='\033[0;36m'
        BOLD='\033[1m'
        RESET='\033[0m'
    fi
}

# Parsowanie argumentów
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --markdown)
                MARKDOWN_MODE=true
                shift
                ;;
            --python-only)
                PYTHON_ONLY=true
                shift
                ;;
            --templates-only)
                TEMPLATES_ONLY=true
                shift
                ;;
            --scss-only)
                SCSS_ONLY=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Nieznany argument: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Użycie: $(basename "$0") [OPCJE]

Skrypt audytu jakości kodu dla projektu BPP.

Opcje:
  --markdown        Wyjście w formacie Markdown (bez kolorów)
  --python-only     Tylko analiza plików Python
  --templates-only  Tylko analiza szablonów HTML
  --scss-only       Tylko analiza plików SCSS
  -h, --help        Wyświetl tę pomoc

Przykłady:
  $(basename "$0")                    # Pełny audyt z kolorami
  $(basename "$0") --markdown > raport.md
  $(basename "$0") --python-only
EOF
}

# Funkcje formatowania
print_header() {
    local title="$1"
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo ""
        echo "## $title"
        echo ""
    else
        echo ""
        echo -e "${BOLD}${BLUE}=== $title ===${RESET}"
        echo ""
    fi
}

print_subheader() {
    local title="$1"
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo ""
        echo "### $title"
        echo ""
    else
        echo -e "${CYAN}--- $title ---${RESET}"
    fi
}

print_critical() {
    local msg="$1"
    COUNT_CRITICAL=$((COUNT_CRITICAL + 1))
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "- **KRYTYCZNY**: $msg"
    else
        echo -e "${RED}${BOLD}[KRYTYCZNY]${RESET} $msg"
    fi
}

print_high() {
    local msg="$1"
    COUNT_HIGH=$((COUNT_HIGH + 1))
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "- **WYSOKI**: $msg"
    else
        echo -e "${RED}[WYSOKI]${RESET} $msg"
    fi
}

print_medium() {
    local msg="$1"
    COUNT_MEDIUM=$((COUNT_MEDIUM + 1))
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "- SREDNI: $msg"
    else
        echo -e "${YELLOW}[SREDNI]${RESET} $msg"
    fi
}

print_low() {
    local msg="$1"
    COUNT_LOW=$((COUNT_LOW + 1))
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "- niski: $msg"
    else
        echo -e "${GREEN}[niski]${RESET} $msg"
    fi
}

print_ok() {
    local msg="$1"
    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "OK: $msg"
    else
        echo -e "${GREEN}[OK]${RESET} $msg"
    fi
}

# ============================================================================
# ANALIZA PYTHON
# ============================================================================

analyze_python() {
    print_header "Analiza plików Python"

    analyze_python_large_files
    analyze_python_complexity
    analyze_python_broad_exceptions
    analyze_python_unsafe_get
    analyze_python_imports
    analyze_test_coverage
}

analyze_python_large_files() {
    print_subheader "Duże pliki Python (>$PYTHON_LINE_LIMIT linii)"

    local found=0
    while IFS= read -r file; do
        local lines
        lines=$(wc -l < "$file" | tr -d ' ')
        local rel_path="${file#$PROJECT_ROOT/}"

        if [[ $lines -gt $PYTHON_LINE_CRITICAL ]]; then
            print_high "$rel_path: $lines linii (krytycznie duży)"
            found=1
        elif [[ $lines -gt $PYTHON_LINE_LIMIT ]]; then
            print_medium "$rel_path: $lines linii"
            found=1
        fi
    done < <(find "$SRC_DIR" -name "*.py" -type f \
        ! -path "*/migrations/*" \
        ! -path "*/__pycache__/*" \
        ! -name "settings.py" \
        2>/dev/null | sort)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak plików przekraczających limit"
    fi
}

analyze_python_complexity() {
    print_subheader "Złożoność cyklomatyczna (>$COMPLEXITY_THRESHOLD)"

    if ! command -v ruff &> /dev/null; then
        echo "UWAGA: ruff nie jest zainstalowany, pomijam analizę złożoności"
        return
    fi

    local output
    output=$(cd "$PROJECT_ROOT" && uv run ruff check --select=C90 "$SRC_DIR" \
        --ignore-noqa \
        --output-format=text 2>/dev/null || true)

    if [[ -z "$output" ]]; then
        print_ok "Brak funkcji z nadmierną złożonością"
        return
    fi

    local found=0
    while IFS= read -r line; do
        if [[ -z "$line" ]]; then
            continue
        fi
        # Filtruj migracje
        if [[ "$line" == *"/migrations/"* ]]; then
            continue
        fi

        # Wyciągnij złożoność z linii typu:
        # src/file.py:10:1: C901 `func` is too complex (15 > 10)
        if [[ "$line" =~ \(([0-9]+)\ \>\ [0-9]+\) ]]; then
            local complexity="${BASH_REMATCH[1]}"
            local rel_line="${line#$PROJECT_ROOT/}"

            if [[ $complexity -gt $COMPLEXITY_CRITICAL ]]; then
                print_high "$rel_line"
                found=1
            else
                print_medium "$rel_line"
                found=1
            fi
        fi
    done <<< "$output"

    if [[ $found -eq 0 ]]; then
        print_ok "Brak funkcji z nadmierną złożonością"
    fi
}

analyze_python_broad_exceptions() {
    print_subheader "Szerokie wyjątki (except: / except Exception:)"

    local found=0

    # except: (bare except)
    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        local rel_path="${file#$PROJECT_ROOT/}"
        print_medium "$rel_path:$line_num - bare except"
        found=1
    done < <(grep -rn "except:" "$SRC_DIR" \
        --include="*.py" \
        --exclude-dir=migrations \
        --exclude-dir=__pycache__ \
        2>/dev/null | grep -v "except:$" | head -50 || true)

    # except Exception:
    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        local rel_path="${file#$PROJECT_ROOT/}"
        print_low "$rel_path:$line_num - except Exception"
        found=1
    done < <(grep -rn "except Exception:" "$SRC_DIR" \
        --include="*.py" \
        --exclude-dir=migrations \
        --exclude-dir=__pycache__ \
        2>/dev/null | head -50 || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak szerokich wyjątków"
    fi
}

analyze_python_unsafe_get() {
    print_subheader "Potencjalnie niebezpieczne objects.get()"

    local found=0

    # Szukaj .objects.get( bez try/except w kontekście
    while IFS=: read -r file line_num content; do
        if [[ -z "$file" ]]; then
            continue
        fi
        local rel_path="${file#$PROJECT_ROOT/}"

        # Sprawdź czy to nie jest w bloku try (uproszczona heurystyka)
        local context
        context=$(sed -n "$((line_num > 3 ? line_num - 3 : 1)),${line_num}p" "$file" 2>/dev/null || true)

        if [[ "$context" != *"try:"* ]] && [[ "$context" != *"get_or_create"* ]]; then
            print_low "$rel_path:$line_num - objects.get() bez widocznego try"
            found=1
        fi
    done < <(grep -rn "\.objects\.get(" "$SRC_DIR" \
        --include="*.py" \
        --exclude-dir=migrations \
        --exclude-dir=__pycache__ \
        --exclude-dir=tests \
        2>/dev/null | head -30 || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak podejrzanych wywołań objects.get()"
    fi
}

analyze_python_imports() {
    print_subheader "Problemy z importami (ruff F401, I)"

    if ! command -v ruff &> /dev/null; then
        echo "UWAGA: ruff nie jest zainstalowany"
        return
    fi

    local output
    output=$(cd "$PROJECT_ROOT" && uv run ruff check --select=F401,I \
        "$SRC_DIR" \
        --output-format=text 2>/dev/null | head -20 || true)

    if [[ -z "$output" ]]; then
        print_ok "Brak problemów z importami"
    else
        local count
        count=$(echo "$output" | wc -l | tr -d ' ')
        print_low "Znaleziono $count problemów z importami (pierwsze 20 poniżej)"
        echo "$output" | while IFS= read -r line; do
            echo "  $line"
        done
    fi
}

analyze_test_coverage() {
    print_subheader "Pokrycie testami (liczba testów na aplikację)"

    local total_test_files=0
    local total_test_functions=0
    local total_app_lines=0
    local total_test_lines=0
    local app_with_tests=0

    # Użyj pliku tymczasowego do przechowywania danych
    local tmpfile
    tmpfile=$(mktemp)

    # Dla każdego katalogu w src/ który jest aplikacją Django
    while IFS= read -r app_dir; do
        local app_name
        app_name=$(basename "$app_dir")

        # Sprawdź czy to aplikacja Django (ma models.py, admin.py, lub tests/)
        if [[ ! -f "$app_dir/models.py" ]] && [[ ! -f "$app_dir/admin.py" ]] && [[ ! -d "$app_dir/tests" ]] && [[ ! -f "$app_dir/tests.py" ]]; then
            continue
        fi

        # Zlicz linie kodu aplikacji (pomijając migracje i testy)
        local app_lines=0
        while IFS= read -r file; do
            local lines
            lines=$(wc -l < "$file" 2>/dev/null | tr -d ' ') || lines=0
            app_lines=$((app_lines + lines))
        done < <(find "$app_dir" -name "*.py" -type f \
            ! -path "*/migrations/*" \
            ! -path "*/tests/*" \
            ! -name "test_*.py" \
            ! -name "tests.py" \
            ! -path "*/__pycache__/*" \
            2>/dev/null)

        # Znajdź pliki testowe w aplikacji
        local test_files=()
        local test_lines=0
        local test_functions=0

        # Dodaj tests.py jeśli istnieje
        if [[ -f "$app_dir/tests.py" ]]; then
            test_files+=("$app_dir/tests.py")
        fi

        # Dodaj wszystkie test_*.py w głównym katalogu aplikacji
        while IFS= read -r test_file; do
            test_files+=("$test_file")
        done < <(find "$app_dir" -maxdepth 1 -name "test_*.py" -type f 2>/dev/null | sort)

        # Dodaj wszystkie pliki z katalogu tests/
        if [[ -d "$app_dir/tests" ]]; then
            while IFS= read -r test_file; do
                test_files+=("$test_file")
            done < <(find "$app_dir/tests" -name "test_*.py" -type f 2>/dev/null | sort)
        fi

        # Jeśli brak plików testowych, pomiń
        if [[ ${#test_files[@]} -eq 0 ]]; then
            continue
        fi

        # Zlicz linie kodu testów i funkcje testowe
        for test_file in "${test_files[@]}"; do
            local lines
            local count
            if [[ -f "$test_file" ]]; then
                lines=$(wc -l < "$test_file" 2>/dev/null | tr -d ' ') || lines=0
                test_lines=$((test_lines + lines))
                count=$(grep -c "^def test_" "$test_file" 2>/dev/null) || count=0
            else
                lines=0
                count=0
            fi
            test_functions=$((test_functions + count))
        done

        # Oblicz ratio
        local ratio=0
        if [[ $app_lines -gt 0 ]]; then
            ratio=$(echo "scale=2; $test_lines / $app_lines" | bc 2>/dev/null) || ratio=0
        fi

        # Zapisz dane do pliku tymczasowego (ratio, app_name, app_lines, test_lines, num_files)
        echo "$ratio $app_name $app_lines $test_lines ${#test_files[@]}" >> "$tmpfile"

        total_app_lines=$((total_app_lines + app_lines))
        total_test_lines=$((total_test_lines + test_lines))
        total_test_files=$((total_test_files + ${#test_files[@]}))
        total_test_functions=$((total_test_functions + test_functions))
        app_with_tests=$((app_with_tests + 1))

    done < <(find "$SRC_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

    # Oblicz całkowite ratio
    local total_ratio=0
    if [[ $total_app_lines -gt 0 ]]; then
        total_ratio=$(echo "scale=2; $total_test_lines / $total_app_lines" | bc 2>/dev/null) || total_ratio=0
    fi

    # Wyświetl nagłówek
    echo ""
    printf "%-35s %-12s %-12s %-10s %-10s\n" "Aplikacja" "Linie app" "Linie test" "Ratio" "Pliki"
    printf "%-35s %-12s %-12s %-10s %-10s\n" "$(printf '%35s' | tr ' ' '-')" "$(printf '%12s' | tr ' ' '-')" "$(printf '%12s' | tr ' ' '-')" "$(printf '%10s' | tr ' ' '-')" "$(printf '%10s' | tr ' ' '-')"

    # Wyświetl posortowane dane
    if [[ -f "$tmpfile" ]] && [[ -s "$tmpfile" ]]; then
        while IFS=' ' read -r ratio app_name app_lines test_lines num_files; do
            printf "%-35s %-12s %-12s %-10s %-10s\n" "$app_name" "$app_lines" "$test_lines" "$ratio" "$num_files"
        done < <(sort -n "$tmpfile")
    fi

    # Wyświetl podsumowanie
    printf "%-35s %-12s %-12s %-10s %-10s\n" "$(printf '%35s' | tr ' ' '-')" "$(printf '%12s' | tr ' ' '-')" "$(printf '%12s' | tr ' ' '-')" "$(printf '%10s' | tr ' ' '-')" "$(printf '%10s' | tr ' ' '-')"
    printf "%-35s %-12s %-12s %-10s %-10s\n" "RAZEM" "$total_app_lines" "$total_test_lines" "$total_ratio" "$total_test_files"
    echo ""
    echo "Liczba aplikacji z testami: $app_with_tests"
    echo "Całkowita liczba funkcji testowych: $total_test_functions"

    if [[ $app_with_tests -lt 10 ]]; then
        print_medium "Tylko $app_with_tests aplikacji ma testy"
    elif [[ $app_with_tests -lt 30 ]]; then
        print_ok "Dobry poziom pokrycia testami ($app_with_tests aplikacji)"
    else
        print_ok "Wysoki poziom pokrycia testami ($app_with_tests aplikacji)"
    fi

    # Usuń plik tymczasowy
    rm -f "$tmpfile"
}

# ============================================================================
# ANALIZA SZABLONÓW HTML
# ============================================================================

analyze_templates() {
    print_header "Analiza szablonów HTML"

    analyze_inline_javascript
    analyze_inline_styles
    analyze_accessibility
}

analyze_inline_javascript() {
    print_subheader "Inline JavaScript (onclick, onchange, etc.)"

    local found=0

    # Szukaj atrybutów onclick, onchange, onsubmit itp.
    local patterns=("onclick=" "onchange=" "onsubmit=" "onload=" "onerror=" \
                    "onkeyup=" "onkeydown=" "onfocus=" "onblur=" "onmouseover=")

    for pattern in "${patterns[@]}"; do
        while IFS=: read -r file line_num content; do
            if [[ -z "$file" ]]; then
                continue
            fi

            # Pomiń 500.html (generowany automatycznie)
            if [[ "$file" == *"/500.html" ]]; then
                continue
            fi

            # Pomiń tinymce/examples (zewnętrzne)
            if [[ "$file" == *"/tinymce/examples/"* ]]; then
                continue
            fi

            # Sprawdź czy event handler używa namespaced funkcji
            # Ignoruj jeśli zawiera window.bpp., window., document., return
            if [[ "$content" =~ window\.[a-zA-Z] ]] || \
               [[ "$content" =~ document\.[a-zA-Z] ]] || \
               [[ "$content" == "return" ]] || \
               [[ "$content" == *".bpp."* ]]; then
                continue
            fi

            local rel_path="${file#$PROJECT_ROOT/}"
            print_medium "$rel_path:$line_num - $pattern"
            found=1
        done < <(grep -rn "$pattern" "$SRC_DIR" \
            --include="*.html" \
            2>/dev/null | head -20 || true)
    done

    # Inline <script> w szablonach (nie static)
    print_subheader "Inline <script> w szablonach"

    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        # Pomiń katalogi static
        if [[ "$file" == *"/static/"* ]]; then
            continue
        fi
        local rel_path="${file#$PROJECT_ROOT/}"
        print_medium "$rel_path:$line_num - inline <script>"
        found=1
    done < <(grep -rn "<script>" "$SRC_DIR" \
        --include="*.html" \
        2>/dev/null | head -30 || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak inline JavaScript"
    fi
}

analyze_inline_styles() {
    print_subheader "Inline styles (style=)"

    local found=0
    local count=0

    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        ((count++))
        if [[ $count -le 20 ]]; then
            local rel_path="${file#$PROJECT_ROOT/}"
            print_low "$rel_path:$line_num - inline style"
        fi
        found=1
    done < <(grep -rn 'style="' "$SRC_DIR" \
        --include="*.html" \
        2>/dev/null || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak inline styles"
    elif [[ $count -gt 20 ]]; then
        echo "  ... i $((count - 20)) więcej"
    fi
}

analyze_accessibility() {
    print_subheader "Dostępność (brak alt w img)"

    local found=0

    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        # Sprawdź czy jest alt
        local line_content
        line_content=$(sed -n "${line_num}p" "$file" 2>/dev/null || true)

        if [[ "$line_content" != *"alt="* ]]; then
            local rel_path="${file#$PROJECT_ROOT/}"
            print_low "$rel_path:$line_num - <img> bez alt"
            found=1
        fi
    done < <(grep -rn "<img " "$SRC_DIR" \
        --include="*.html" \
        2>/dev/null | head -30 || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Wszystkie obrazki mają atrybut alt"
    fi
}

# ============================================================================
# ANALIZA SCSS
# ============================================================================

analyze_scss() {
    print_header "Analiza plików SCSS"

    analyze_scss_large_files
    analyze_scss_important
}

analyze_scss_large_files() {
    print_subheader "Duże pliki SCSS (>$SCSS_LINE_LIMIT linii)"

    local found=0
    while IFS= read -r file; do
        local lines
        lines=$(wc -l < "$file" | tr -d ' ')
        local rel_path="${file#$PROJECT_ROOT/}"

        if [[ $lines -gt $SCSS_LINE_LIMIT ]]; then
            print_medium "$rel_path: $lines linii"
            found=1
        fi
    done < <(find "$SRC_DIR" -name "*.scss" -type f 2>/dev/null | sort)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak plików SCSS przekraczających limit"
    fi
}

analyze_scss_important() {
    print_subheader "Nadużycia !important"

    local found=0
    local count=0

    while IFS=: read -r file line_num _; do
        if [[ -z "$file" ]]; then
            continue
        fi
        ((count++))
        if [[ $count -le 15 ]]; then
            local rel_path="${file#$PROJECT_ROOT/}"
            print_low "$rel_path:$line_num - !important"
        fi
        found=1
    done < <(grep -rn "!important" "$SRC_DIR" \
        --include="*.scss" \
        2>/dev/null || true)

    if [[ $found -eq 0 ]]; then
        print_ok "Brak nadużyć !important"
    elif [[ $count -gt 15 ]]; then
        echo "  ... i $((count - 15)) więcej (łącznie: $count)"
    fi
}

# ============================================================================
# ANALIZA OGÓLNA
# ============================================================================

analyze_general() {
    print_header "Analiza ogólna"

    analyze_todo_fixme
    analyze_hardcoded_secrets
}

analyze_todo_fixme() {
    print_subheader "TODO/FIXME komentarze"

    local todo_count=0
    local fixme_count=0

    todo_count=$(grep -r "TODO" "$SRC_DIR" \
        --include="*.py" \
        --exclude-dir=migrations \
        --exclude-dir=__pycache__ \
        2>/dev/null | wc -l | tr -d ' ' || echo "0")

    fixme_count=$(grep -r "FIXME" "$SRC_DIR" \
        --include="*.py" \
        --exclude-dir=migrations \
        --exclude-dir=__pycache__ \
        2>/dev/null | wc -l | tr -d ' ' || echo "0")

    if [[ $fixme_count -gt 0 ]]; then
        print_low "Znaleziono $fixme_count komentarzy FIXME"
    fi

    if [[ $todo_count -gt 0 ]]; then
        print_low "Znaleziono $todo_count komentarzy TODO"
    fi

    if [[ $todo_count -eq 0 ]] && [[ $fixme_count -eq 0 ]]; then
        print_ok "Brak TODO/FIXME"
    fi
}

analyze_hardcoded_secrets() {
    print_subheader "Potencjalne hardcoded secrets"

    local found=0

    # Wzorce sugerujące hardcoded secrets
    local patterns=(
        "password.*=.*['\"]"
        "secret.*=.*['\"]"
        "api_key.*=.*['\"]"
        "token.*=.*['\"][A-Za-z0-9]"
    )

    for pattern in "${patterns[@]}"; do
        while IFS=: read -r file line_num content; do
            if [[ -z "$file" ]]; then
                continue
            fi
            # Pomiń pliki testowe i ustawienia
            if [[ "$file" == *"test"* ]] || [[ "$file" == *"settings"* ]]; then
                continue
            fi
            # Pomiń jeśli to odwołanie do env/config
            if [[ "$content" == *"os.environ"* ]] || \
               [[ "$content" == *"getenv"* ]] || \
               [[ "$content" == *"config"* ]]; then
                continue
            fi

            local rel_path="${file#$PROJECT_ROOT/}"
            print_high "$rel_path:$line_num - potencjalny hardcoded secret"
            found=1
        done < <(grep -rniE "$pattern" "$SRC_DIR" \
            --include="*.py" \
            --exclude-dir=migrations \
            --exclude-dir=__pycache__ \
            2>/dev/null | head -10 || true)
    done

    if [[ $found -eq 0 ]]; then
        print_ok "Nie wykryto oczywistych hardcoded secrets"
    fi
}

# ============================================================================
# PODSUMOWANIE
# ============================================================================

print_summary() {
    print_header "Podsumowanie audytu"

    local total=$((COUNT_CRITICAL + COUNT_HIGH + COUNT_MEDIUM + COUNT_LOW))

    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "| Priorytet | Liczba |"
        echo "|-----------|--------|"
        echo "| Krytyczny | ${COUNT_CRITICAL} |"
        echo "| Wysoki    | ${COUNT_HIGH} |"
        echo "| Sredni    | ${COUNT_MEDIUM} |"
        echo "| Niski     | ${COUNT_LOW} |"
        echo "| **Razem** | **$total** |"
    else
        echo -e "${BOLD}Znalezione problemy:${RESET}"
        echo -e "  ${RED}${BOLD}Krytyczne:${RESET} ${COUNT_CRITICAL}"
        echo -e "  ${RED}Wysokie:${RESET}   ${COUNT_HIGH}"
        echo -e "  ${YELLOW}Średnie:${RESET}   ${COUNT_MEDIUM}"
        echo -e "  ${GREEN}Niskie:${RESET}    ${COUNT_LOW}"
        echo -e "  ${BOLD}Razem:${RESET}     $total"
    fi

    echo ""

    if [[ ${COUNT_CRITICAL} -gt 0 ]]; then
        echo "UWAGA: Znaleziono problemy krytyczne wymagające natychmiastowej uwagi!"
    elif [[ ${COUNT_HIGH} -gt 0 ]]; then
        echo "Zalecenie: Rozwiąż problemy o wysokim priorytecie."
    elif [[ $total -gt 0 ]]; then
        echo "Kod w dobrym stanie, ale jest miejsce na poprawę."
    else
        echo "Kod w doskonałym stanie!"
    fi
}

# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

main() {
    parse_args "$@"
    setup_colors

    if [[ "$MARKDOWN_MODE" == "true" ]]; then
        echo "# Raport audytu jakości kodu BPP"
        echo ""
        echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "Katalog: \`$SRC_DIR\`"
    else
        echo -e "${BOLD}Audyt jakości kodu BPP${RESET}"
        echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Katalog: $SRC_DIR"
    fi

    # Określ które analizy uruchomić
    local run_python=true
    local run_templates=true
    local run_scss=true
    local run_general=true

    if [[ "$PYTHON_ONLY" == "true" ]]; then
        run_templates=false
        run_scss=false
    elif [[ "$TEMPLATES_ONLY" == "true" ]]; then
        run_python=false
        run_scss=false
    elif [[ "$SCSS_ONLY" == "true" ]]; then
        run_python=false
        run_templates=false
    fi

    # Uruchom analizy
    [[ "$run_python" == "true" ]] && analyze_python
    [[ "$run_templates" == "true" ]] && analyze_templates
    [[ "$run_scss" == "true" ]] && analyze_scss
    [[ "$run_general" == "true" ]] && analyze_general

    print_summary
}

main "$@"
