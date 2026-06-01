# Reorganizacja dokumentacji MkDocs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przekształcić płaski katalog `docs/` w strukturę audience-first
(foldery per-odbiorca), przywrócić osierocone dev-docs jako publikowaną
sekcję, naprawić 15 artefaktów migracji RST→MkDocs.

**Architecture:** `git mv` plików do podkatalogów + przepisanie relatywnych
linków i ścieżek obrazków + restore 3 plików z historii git + przepisanie
`nav` w `mkdocs.yml` + nowy hub `index.md`. Brama poprawności:
`mkdocs build --strict` (broken link = błąd builda).

**Tech Stack:** MkDocs Material, `mkdocs build --strict`, git, uv.

**Worktree:** `~/Programowanie/bpp-docs-restructure` (branch `docs/restructure`).
Wszystkie komendy uruchamiaj z tego katalogu.

**Spec:** `docs/superpowers/specs/2026-06-01-docs-restructure-design.md`

---

## Mapa zmian plików (referencja)

Przeniesienia (`git mv stary nowy`):

| Stary (docs/)                 | Nowy (docs/)                              |
|-------------------------------|-------------------------------------------|
| edycja_uczelnia.md            | uzytkownik/uczelnia.md                    |
| edycja_jednostka.md           | uzytkownik/jednostki.md                   |
| edycja_autor.md               | uzytkownik/autorzy.md                     |
| edycja_wydawnictwo.md         | uzytkownik/wydawnictwa.md                 |
| wyszukiwanie_redagowanie.md   | uzytkownik/wyszukiwanie-redagowanie.md    |
| raporty_rankingi.md           | uzytkownik/raporty-rankingi.md            |
| sloty.md                      | uzytkownik/sloty.md                       |
| usage_admin.md                | administrator/ogolna.md                   |
| importer_publikacji.md        | administrator/importer-publikacji.md      |
| import_pracownikow.md         | administrator/import-pracownikow.md       |
| zglos_publikacje.md           | administrator/zglaszanie-publikacji.md    |
| konfiguracja_pbn.md           | administrator/konfiguracja-pbn.md         |
| pbn.md                        | administrator/integracja-pbn.md           |
| advanced.md                   | administrator/zaawansowane.md             |
| api.md                        | api/index.md                              |
| contributing.md               | deweloper/rozwijanie-projektu.md          |
| MACOS_WEASYPRINT.md           | deweloper/weasyprint-macos.md             |
| CHANNELS_BROADCAST_FLAKE.md   | deweloper/testy-channels-broadcast.md     |
| SECURITY.md                   | bezpieczenstwo/polityka.md                |
| SECURITY_PRACTICES.md         | bezpieczenstwo/praktyki.md                |
| authors.md                    | o-projekcie/autorzy.md                    |
| history.md                    | o-projekcie/historia.md                   |

Restore z historii git (commit `6c8e383e8^`):

| Źródło (git)                        | Nowy (docs/)               |
|-------------------------------------|----------------------------|
| 6c8e383e8^:docs/CODEBASE_MAP.md     | deweloper/mapa-kodu.md     |
| 6c8e383e8^:docs/COMMANDS.md         | deweloper/polecenia.md     |
| 6c8e383e8^:docs/CSS_BUILD.md        | deweloper/budowanie-css.md |

Nowy plik: `deweloper/index.md`. Usuwane z nav: `readme.md` (plik kasujemy).

---

## Task 1: Baseline builda + struktura folderów

**Files:**
- Create: `docs/uzytkownik/.gitkeep` (tymczasowo, do usunięcia po git mv)

- [ ] **Step 1: Potwierdź zielony build PRZED zmianami**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
uv run --with-requirements docs/requirements.txt mkdocs build --strict 2>&1 | tail -15
```
Expected: kończy się `INFO - Documentation built in ...`, brak `Aborted with N warnings`.
Jeśli już teraz są warningi — zanotuj je (to baseline, nie wprowadzaj ich
jako regresji), ale build musi zwrócić exit 0.

- [ ] **Step 2: Utwórz katalogi docelowe**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
mkdir -p docs/uzytkownik docs/administrator docs/api docs/deweloper \
         docs/bezpieczenstwo docs/o-projekcie
```
Expected: brak outputu (sukces).

(Nie commitujemy pustych folderów — wypełni je `git mv` w kolejnych
taskach. Brak `.gitkeep`.)

---

## Task 2: Przenieś dokumenty użytkownika (`git mv`)

**Files:** patrz tabela — 7 plików → `docs/uzytkownik/`.

- [ ] **Step 1: git mv plików użytkownika**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git mv docs/edycja_uczelnia.md          docs/uzytkownik/uczelnia.md
git mv docs/edycja_jednostka.md         docs/uzytkownik/jednostki.md
git mv docs/edycja_autor.md             docs/uzytkownik/autorzy.md
git mv docs/edycja_wydawnictwo.md       docs/uzytkownik/wydawnictwa.md
git mv docs/wyszukiwanie_redagowanie.md docs/uzytkownik/wyszukiwanie-redagowanie.md
git mv docs/raporty_rankingi.md         docs/uzytkownik/raporty-rankingi.md
git mv docs/sloty.md                    docs/uzytkownik/sloty.md
```
Expected: brak outputu.

- [ ] **Step 2: Napraw ścieżki obrazków (`images/` → `../images/`)**

Pliki z obrazkami: `uczelnia.md`, `autorzy.md`, `wydawnictwa.md`,
`wyszukiwanie-redagowanie.md`. Dla każdego zamień `](images/` na `](../images/`.

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' 's#](images/#](../images/#g' \
  docs/uzytkownik/uczelnia.md \
  docs/uzytkownik/autorzy.md \
  docs/uzytkownik/wydawnictwa.md \
  docs/uzytkownik/wyszukiwanie-redagowanie.md
```
Expected: brak outputu.

- [ ] **Step 3: Napraw linki wewnętrzne w jednostki.md**

Plik `docs/uzytkownik/jednostki.md` linkuje do importu pracowników
(teraz w `administrator/`). Zamień:
- `](import_pracownikow.md)` → `](../administrator/import-pracownikow.md)`
- `](import_pracownikow.md#odpinanie-nieaktualnych-miejsc-pracy)` →
  `](../administrator/import-pracownikow.md#odpinanie-nieaktualnych-miejsc-pracy)`

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' 's#](import_pracownikow.md#](../administrator/import-pracownikow.md#g' \
  docs/uzytkownik/jednostki.md
```
Expected: brak outputu.

- [ ] **Step 4: Weryfikacja braku starych ścieżek**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\]\(images/|\]\(import_pracownikow\.md' docs/uzytkownik/ || echo OK
```
Expected: `OK` (żadnych starych ścieżek).

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/uzytkownik
git commit -m "docs(restructure): przenies instrukcje uzytkownika do uzytkownik/"
```

---

## Task 3: Przenieś dokumenty administratora (`git mv`)

**Files:** 7 plików → `docs/administrator/`.

- [ ] **Step 1: git mv plików administratora**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git mv docs/usage_admin.md          docs/administrator/ogolna.md
git mv docs/importer_publikacji.md  docs/administrator/importer-publikacji.md
git mv docs/import_pracownikow.md   docs/administrator/import-pracownikow.md
git mv docs/zglos_publikacje.md     docs/administrator/zglaszanie-publikacji.md
git mv docs/konfiguracja_pbn.md     docs/administrator/konfiguracja-pbn.md
git mv docs/pbn.md                  docs/administrator/integracja-pbn.md
git mv docs/advanced.md             docs/administrator/zaawansowane.md
```
Expected: brak outputu.

- [ ] **Step 2: Napraw ścieżki obrazków**

Pliki z obrazkami: `ogolna.md`, `importer-publikacji.md` (sprawdź),
`import-pracownikow.md`, `zglaszanie-publikacji.md`.

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' 's#](images/#](../images/#g' \
  docs/administrator/ogolna.md \
  docs/administrator/importer-publikacji.md \
  docs/administrator/import-pracownikow.md \
  docs/administrator/zglaszanie-publikacji.md
```
Expected: brak outputu.

- [ ] **Step 3: Napraw linki wewnętrzne**

`ogolna.md` → link do `konfiguracja_pbn.md` (ten sam folder teraz):
- `](konfiguracja_pbn.md)` → `](konfiguracja-pbn.md)`

`import-pracownikow.md` → linki do plików użytkownika:
- `](edycja_uczelnia.md#obca-jednostka)` →
  `](../uzytkownik/uczelnia.md#obca-jednostka)`
- `](edycja_autor.md#pole-aktualne-miejsce-pracy-dla-autora)` →
  `](../uzytkownik/autorzy.md#pole-aktualne-miejsce-pracy-dla-autora)`

`zglaszanie-publikacji.md` → linki:
- `](advanced.md#konfiguracja-ldap-activedirectory)` →
  `](zaawansowane.md#konfiguracja-ldap-activedirectory)`
- `](edycja_uczelnia.md)` (×2) → `](../uzytkownik/uczelnia.md)`

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' 's#](konfiguracja_pbn.md)#](konfiguracja-pbn.md)#g' \
  docs/administrator/ogolna.md
sed -i '' \
  -e 's#](edycja_uczelnia.md#](../uzytkownik/uczelnia.md#g' \
  -e 's#](edycja_autor.md#](../uzytkownik/autorzy.md#g' \
  docs/administrator/import-pracownikow.md
sed -i '' \
  -e 's#](advanced.md#](zaawansowane.md#g' \
  -e 's#](edycja_uczelnia.md)#](../uzytkownik/uczelnia.md)#g' \
  docs/administrator/zglaszanie-publikacji.md
```
Expected: brak outputu.

- [ ] **Step 4: Weryfikacja braku starych ścieżek**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\]\(images/|edycja_uczelnia\.md|edycja_autor\.md|konfiguracja_pbn\.md|\]\(advanced\.md' docs/administrator/ || echo OK
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/administrator
git commit -m "docs(restructure): przenies instrukcje administratora do administrator/"
```

---

## Task 4: Przenieś dokument API

**Files:** `api.md` → `docs/api/index.md`.

- [ ] **Step 1: git mv**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git mv docs/api.md docs/api/index.md
```

- [ ] **Step 2: Napraw ścieżki obrazków**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' 's#](images/#](../images/#g' docs/api/index.md
```
Expected: brak outputu. (`api.md` nie miało linków do innych stron .md,
tylko obrazki — naprawa tyld w Task 8.)

- [ ] **Step 3: Weryfikacja**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -nE '\]\(images/' docs/api/index.md || echo OK
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/api
git commit -m "docs(restructure): przenies api.md do api/index.md"
```

---

## Task 5: Sekcja deweloperska — restore + nowe pliki

**Files:**
- Create: `docs/deweloper/mapa-kodu.md` (restore)
- Create: `docs/deweloper/polecenia.md` (restore)
- Create: `docs/deweloper/budowanie-css.md` (restore)
- Create: `docs/deweloper/index.md` (nowy landing)
- Move: `contributing.md`, `MACOS_WEASYPRINT.md`, `CHANNELS_BROADCAST_FLAKE.md`

- [ ] **Step 1: Restore 3 plików z historii git**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git show 6c8e383e8^:docs/CODEBASE_MAP.md > docs/deweloper/mapa-kodu.md
git show 6c8e383e8^:docs/COMMANDS.md     > docs/deweloper/polecenia.md
git show 6c8e383e8^:docs/CSS_BUILD.md    > docs/deweloper/budowanie-css.md
wc -l docs/deweloper/mapa-kodu.md docs/deweloper/polecenia.md docs/deweloper/budowanie-css.md
```
Expected: ~557 / ~117 / ~72 linii.

- [ ] **Step 2: git mv pozostałych dev-docs**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git mv docs/contributing.md             docs/deweloper/rozwijanie-projektu.md
git mv docs/MACOS_WEASYPRINT.md         docs/deweloper/weasyprint-macos.md
git mv docs/CHANNELS_BROADCAST_FLAKE.md docs/deweloper/testy-channels-broadcast.md
```

- [ ] **Step 3: Banner w mapa-kodu.md (generowane maszynowo)**

Plik zaczyna się od frontmatter YAML (`---` … `---`) i nagłówka
`# BPP Codebase Map`. Wstaw admonicję ZARAZ PO linii `# BPP Codebase Map`
(użyj Edit tool: znajdź pierwsze wystąpienie `# BPP Codebase Map\n` i dopisz
poniżej pustą linię + blok):

```markdown
!!! warning "Plik generowany maszynowo"
    Ta mapa jest generowana automatycznie (Cartographer). **Nie edytuj jej
    ręcznie** — zmiany zostaną nadpisane przy regeneracji. Pole `last_mapped`
    we frontmatterze wskazuje datę ostatniej regeneracji; jeśli jest stare,
    traktuj treść jako orientacyjną. To dokumentacja dla **dewelopera i agenta
    AI**, nie dla użytkownika systemu.
```

- [ ] **Step 4: Utwórz deweloper/index.md (landing)**

Create `docs/deweloper/index.md`:

```markdown
# Dla deweloperów i agentów

!!! note "Dla kogo jest ta sekcja"
    To dokumentacja techniczna dla **deweloperów** rozwijających BPP oraz dla
    **agentów AI** (np. Claude Code) pracujących nad kodem. **Nie** jest to
    instrukcja dla bibliotekarzy ani administratorów wdrożenia — tych szukaj
    w sekcjach „Instrukcja użytkownika" i „Instrukcja administratora".

Źródłem prawdy o zasadach pracy z kodem jest plik
[`CLAUDE.md`](https://github.com/iplweb/bpp/blob/dev/CLAUDE.md) w korzeniu
repozytorium. Poniższe strony rozwijają wybrane tematy:

- [Mapa kodu](mapa-kodu.md) — architektura i rozmieszczenie modułów
  (generowane maszynowo).
- [Polecenia](polecenia.md) — referencja komend (testy, build, Celery,
  zarządzanie).
- [Budowanie CSS/SCSS](budowanie-css.md) — pipeline frontendu (Grunt,
  Foundation).
- [Rozwijanie projektu](rozwijanie-projektu.md) — jak współtworzyć.
- [WeasyPrint na macOS](weasyprint-macos.md) — konfiguracja PDF lokalnie.
- [Testy: Channels broadcast (flake)](testy-channels-broadcast.md) —
  diagnostyka niestabilnego testu.
```

- [ ] **Step 5: Weryfikacja**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
ls docs/deweloper/
grep -c "generowany maszynowo" docs/deweloper/mapa-kodu.md
```
Expected: 7 plików (index, mapa-kodu, polecenia, budowanie-css,
rozwijanie-projektu, weasyprint-macos, testy-channels-broadcast);
`grep` zwraca `1`.

- [ ] **Step 6: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/deweloper
git commit -m "docs(restructure): sekcja deweloper/ — restore mapa-kodu/polecenia/budowanie-css + landing"
```

---

## Task 6: Bezpieczeństwo + O projekcie

**Files:** 2 + 2 pliki.

- [ ] **Step 1: git mv**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git mv docs/SECURITY.md           docs/bezpieczenstwo/polityka.md
git mv docs/SECURITY_PRACTICES.md docs/bezpieczenstwo/praktyki.md
git mv docs/authors.md            docs/o-projekcie/autorzy.md
git mv docs/history.md            docs/o-projekcie/historia.md
```

- [ ] **Step 2: Sprawdź obrazki/linki (te pliki ich nie mają, ale potwierdź)**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\]\((images/|[a-z_]+\.md)' docs/bezpieczenstwo/ docs/o-projekcie/ || echo OK
```
Expected: `OK`. (Jeśli coś wyjdzie — napraw analogicznie: `images/` →
`../images/`, linki .md → nowa ścieżka.)

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/bezpieczenstwo docs/o-projekcie
git commit -m "docs(restructure): bezpieczenstwo/ + o-projekcie/"
```

---

## Task 7: Hub index.md + usunięcie readme.md

**Files:**
- Modify: `docs/index.md`
- Delete: `docs/readme.md`

- [ ] **Step 1: Skasuj readme.md**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git rm docs/readme.md
```

- [ ] **Step 2: Przepisz docs/index.md na hub**

Zastąp CAŁĄ zawartość `docs/index.md` poniższym (Write tool):

```markdown
# Bibliografia Publikacji Pracowników

System informatyczny do zarządzania bibliografią publikacji pracowników
naukowych. Oprogramowanie przeznaczone jest dla bibliotek naukowych
i uniwersyteckich w Polsce.

Oprogramowanie dystrybuowane jest na zasadach otwartoźródłowej
[licencji MIT](https://pl.wikipedia.org/wiki/Licencja_MIT). Repozytorium
projektu: [github.com/iplweb/bpp](https://github.com/iplweb/bpp). Pełne
README znajduje się
[w korzeniu repozytorium](https://github.com/iplweb/bpp/blob/dev/README.md).

## Wybierz sekcję

Dokumentacja jest podzielona według odbiorcy.

### 📘 Instrukcja użytkownika

Codzienne czynności redakcyjne — dla bibliotekarzy i redaktorów.

- [Uczelnia](uzytkownik/uczelnia.md)
- [Jednostki](uzytkownik/jednostki.md)
- [Autorzy](uzytkownik/autorzy.md)
- [Wydawnictwa](uzytkownik/wydawnictwa.md)
- [Wyszukiwanie i redagowanie](uzytkownik/wyszukiwanie-redagowanie.md)
- [Raporty i rankingi](uzytkownik/raporty-rankingi.md)
- [Sloty](uzytkownik/sloty.md)

### 🛠️ Instrukcja administratora

Konfiguracja, importy i integracje — dla administratorów wdrożenia.

- [Konfiguracja ogólna](administrator/ogolna.md)
- [Importer publikacji](administrator/importer-publikacji.md)
- [Import pracowników](administrator/import-pracownikow.md)
- [Zgłaszanie publikacji](administrator/zglaszanie-publikacji.md)
- [Konfiguracja PBN](administrator/konfiguracja-pbn.md)
- [Integracja z PBN](administrator/integracja-pbn.md)
- [Konfiguracja zaawansowana](administrator/zaawansowane.md)

### 🔌 API

- [REST API — pobieranie danych](api/index.md)

### 💻 Dla deweloperów i agentów

Dokumentacja techniczna — dla deweloperów i agentów AI, nie dla
użytkowników końcowych.

- [Przegląd sekcji deweloperskiej](deweloper/index.md)

### 🔒 Bezpieczeństwo

- [Polityka bezpieczeństwa](bezpieczenstwo/polityka.md)
- [Praktyki bezpieczeństwa](bezpieczenstwo/praktyki.md)

### ℹ️ O projekcie

- [Autorzy](o-projekcie/autorzy.md)
- [Historia zmian](o-projekcie/historia.md)
```

- [ ] **Step 3: Weryfikacja braku starych płaskich linków**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -nE '\]\((edycja_|usage_admin|importer_|import_pracownikow|zglos_|konfiguracja_pbn|raporty_|wyszukiwanie_|advanced|pbn|api|contributing|authors|history|readme)\.md' docs/index.md || echo OK
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/index.md docs/readme.md
git commit -m "docs(restructure): index.md jako hub per-odbiorca, usun readme.md"
```

---

## Task 8: Napraw artefakty migracji RST (tyldy → nagłówki h3)

**Files:**
- Modify: `docs/api/index.md` (10 miejsc)
- Modify: `docs/administrator/ogolna.md` (5 nagłówków + 3 listy)

Każdy artefakt to para linii: tekst nagłówka, a pod nim linia
`\~\~\~\~…`. Naprawa = zostaw tekst, zamień go na `### tekst`, usuń linię tyld.

- [ ] **Step 1: api/index.md — zamień 10 nagłówków na ### i usuń linie tyld**

Dla każdego użyj Edit tool. Pary (tekst → nowy nagłówek), w każdej usuń
linię `\~\~…` bezpośrednio pod nią:

1. `Główne endpoint'y API` → `### Główne endpoint'y API`
2. `Przykłady użycia CURL` → `### Przykłady użycia CURL`
3. `Przykłady użycia w Postman` → `### Przykłady użycia w Postman`
4. `Format odpowiedzi` (pierwsze wyst., ~l.192) → `### Format odpowiedzi`
5. `Parametry filtrowania` → `### Parametry filtrowania`
6. `Paginacja` → `### Paginacja`
7. `Funkcjonalność` → `### Funkcjonalność`
8. `Format odpowiedzi` (drugie wyst., ~l.272) → `### Format odpowiedzi`
9. `Przykład użycia CURL` → `### Przykład użycia CURL`
10. `Uwagi dotyczące CORS` → `### Uwagi dotyczące CORS`

Praktyczny sposób (sed): usuń wszystkie linie złożone wyłącznie z `\~`,
a nagłówki podnieś osobno. Bezpieczniej dwuetapowo:

```bash
cd ~/Programowanie/bpp-docs-restructure
# 2a: usuń linie będące wyłącznie sekwencją \~ (escaped tyldy)
sed -i '' -E '/^(\\~)+$/d' docs/api/index.md
```
Po tym kroku linie nagłówków zostają jako zwykły tekst. Teraz podnieś je
do `###` (Edit tool, dokładny tekst → `### tekst`), dla każdego z 10 tytułów
powyżej. Uwaga: „Format odpowiedzi" i „Przykład/Przykłady użycia CURL"
występują wielokrotnie — edytuj z kontekstem (użyj `replace_all` tylko gdy
wszystkie wystąpienia mają stać się `###`; w przeciwnym razie edytuj
pojedynczo z otaczającą linią).

- [ ] **Step 2: ogolna.md — analogicznie 5 nagłówków**

```bash
cd ~/Programowanie/bpp-docs-restructure
sed -i '' -E '/^(\\~)+$/d' docs/administrator/ogolna.md
```
Następnie podnieś do `###` (Edit tool):
1. `Dostępne charaktery CrossRef API`
2. `Konfiguracja mapowania w module Redagowania`
3. `Ważne zasady mapowania`
4. `Przykłady typowych mapowań`
5. `Weryfikacja poprawności mapowania`

- [ ] **Step 3: ogolna.md — napraw 3 zescape'owane punkty listy**

Linie zaczynające się od `    \* ` to lista RST. Zamień wiodące `\*` na
markdownowy `-` (Edit tool, każda z 3 linii):
- `    \* Mapowanie jest opcjonalne …` → `    - Mapowanie jest opcjonalne …`
- `    \* Rekordy bez mapowania …` → `    - Rekordy bez mapowania …`
- `    \* Zmiana mapowania …` → `    - Zmiana mapowania …`

(`\[brak zamapowania\]` w treści zostaw — w markdown renderuje się jako
literalne `[brak zamapowania]`, co jest poprawne.)

- [ ] **Step 4: Weryfikacja — zero artefaktów**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\\~|^\s*\\\*' docs/ || echo "OK - brak artefaktow"
echo "--- nowe naglowki h3 w api ---"
grep -cE "^### " docs/api/index.md
```
Expected: `OK - brak artefaktow`; `grep -c` w api ≥ 10.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add -A docs/api/index.md docs/administrator/ogolna.md
git commit -m "docs(fix): napraw artefakty migracji RST (~~~~ -> ### , \\* -> - listy)"
```

---

## Task 9: Przepisz nav w mkdocs.yml

**Files:**
- Modify: `mkdocs.yml` (sekcja `nav:`)

- [ ] **Step 1: Zastąp blok `nav:` w mkdocs.yml**

Użyj Edit tool — zastąp obecny blok `nav:` (od linii `nav:` do końca pliku)
poniższym:

```yaml
nav:
  - Start: index.md
  - Instrukcja użytkownika:
      - Uczelnia: uzytkownik/uczelnia.md
      - Jednostki: uzytkownik/jednostki.md
      - Autorzy: uzytkownik/autorzy.md
      - Wydawnictwa: uzytkownik/wydawnictwa.md
      - Wyszukiwanie i redagowanie: uzytkownik/wyszukiwanie-redagowanie.md
      - Raporty i rankingi: uzytkownik/raporty-rankingi.md
      - Sloty: uzytkownik/sloty.md
  - Instrukcja administratora:
      - Konfiguracja ogólna: administrator/ogolna.md
      - Importer publikacji: administrator/importer-publikacji.md
      - Import pracowników: administrator/import-pracownikow.md
      - Zgłaszanie publikacji: administrator/zglaszanie-publikacji.md
      - Konfiguracja PBN: administrator/konfiguracja-pbn.md
      - Integracja z PBN: administrator/integracja-pbn.md
      - Konfiguracja zaawansowana: administrator/zaawansowane.md
  - API: api/index.md
  - Dla deweloperów i agentów:
      - deweloper/index.md
      - Mapa kodu: deweloper/mapa-kodu.md
      - Polecenia: deweloper/polecenia.md
      - Budowanie CSS/SCSS: deweloper/budowanie-css.md
      - Rozwijanie projektu: deweloper/rozwijanie-projektu.md
      - WeasyPrint na macOS: deweloper/weasyprint-macos.md
      - Channels broadcast (flake): deweloper/testy-channels-broadcast.md
  - Bezpieczeństwo:
      - Polityka bezpieczeństwa: bezpieczenstwo/polityka.md
      - Praktyki bezpieczeństwa: bezpieczenstwo/praktyki.md
  - O projekcie:
      - Autorzy: o-projekcie/autorzy.md
      - Historia zmian: o-projekcie/historia.md
```

(`deweloper/index.md` jako pierwsza pozycja sekcji działa jako jej strona
przeglądowa dzięki włączonemu `navigation.indexes`.)

- [ ] **Step 2: PIERWSZY pełny strict build (brama poprawności)**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
uv run --with-requirements docs/requirements.txt mkdocs build --strict 2>&1 | tail -25
```
Expected: `Documentation built in ...`, **zero** `WARNING` o broken links /
„not found in nav". Jeśli pojawi się „contains a link … target not found"
— wróć do taska, gdzie ten plik był ruszany, i popraw ścieżkę. Jeśli
„pages exist … not in nav" — dodaj brakujący plik do nav (Step 1).

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add mkdocs.yml
git commit -m "docs(restructure): przepisz nav na strukture audience-first"
```

---

## Task 10: Zaktualizuj referencje w CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (3 linie na górze, sekcja Project Overview)

- [ ] **Step 1: Podmień 3 linki dev-docs**

Edit tool — zamień dokładnie te trzy linie:

```
- Architecture: [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md)
- Commands reference: [docs/COMMANDS.md](docs/COMMANDS.md)
- CSS/SCSS build: [docs/CSS_BUILD.md](docs/CSS_BUILD.md)
```

na:

```
- Architecture: [docs/deweloper/mapa-kodu.md](docs/deweloper/mapa-kodu.md)
- Commands reference: [docs/deweloper/polecenia.md](docs/deweloper/polecenia.md)
- CSS/SCSS build: [docs/deweloper/budowanie-css.md](docs/deweloper/budowanie-css.md)
```

- [ ] **Step 2: Weryfikacja**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -nE 'CODEBASE_MAP\.md|COMMANDS\.md|CSS_BUILD\.md' CLAUDE.md && echo "BLAD: stare sciezki" || echo OK
grep -nE 'docs/deweloper/(mapa-kodu|polecenia|budowanie-css)\.md' CLAUDE.md
```
Expected: `OK` + 3 trafienia z nowymi ścieżkami.

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/bpp-docs-restructure
git add CLAUDE.md
git commit -m "docs: zaktualizuj linki CLAUDE.md na docs/deweloper/* (naprawiony kontrakt)"
```

---

## Task 11: Akceptacja końcowa

**Files:** brak zmian — tylko weryfikacja.

- [ ] **Step 1: Pełny strict build**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
uv run --with-requirements docs/requirements.txt mkdocs build --strict 2>&1 | tail -20
```
Expected: `Documentation built in ...`, exit 0, zero warningów.

- [ ] **Step 2: Brak artefaktów RST w całym docs/**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\\~' docs/ && echo "BLAD" || echo "OK - brak tyld"
```
Expected: `OK - brak tyld`.

- [ ] **Step 3: Brak osieroconych starych ścieżek w nav i treści**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
grep -rnE '\]\(images/' docs/ && echo "BLAD: nie-przedrostkowane obrazki" || echo "OK images"
ls docs/*.md
```
Expected: `OK images`; `ls docs/*.md` pokazuje WYŁĄCZNIE `docs/index.md`
(wszystko inne w podfolderach).

- [ ] **Step 4: Wizualny sanity-check renderu**

Run (podgląd lokalny):
```bash
cd ~/Programowanie/bpp-docs-restructure
uv run --with-requirements docs/requirements.txt mkdocs serve 2>&1 &
sleep 4
```
Otwórz `http://127.0.0.1:8000/api/` i potwierdź: zniknęły rzędy tyld,
nagłówki „Główne endpoint'y API" itd. są nagłówkami h3 i widnieją w
prawym spisie treści. Sprawdź też `/deweloper/` (landing) i kilka stron
z obrazkami (`/uzytkownik/uczelnia/`). Zatrzymaj serwer: `kill %1`.

- [ ] **Step 5: Git status czysty**

Run:
```bash
cd ~/Programowanie/bpp-docs-restructure
git status --short
git log --oneline origin/dev..HEAD
```
Expected: brak niezacommitowanych zmian; lista commitów Task 2–10.

---

## Self-review (autor planu)

**Pokrycie spec:**
- WS1 przenosiny → Task 2,3,4,5,6. ✓
- WS2 restore dev-docs → Task 5 (Step 1). ✓
- WS3 deweloper/index.md → Task 5 (Step 4). ✓
- WS4 artefakty RST → Task 8. ✓
- WS5 linki wewnętrzne → Task 2 (Step 3), Task 3 (Step 3), Task 7. ✓
- WS6 mkdocs.yml → Task 9. ✓
- WS7 CLAUDE.md → Task 10. ✓
- Kryterium `mkdocs build --strict` → Task 9 (Step 2), Task 11 (Step 1). ✓
- Banner mapa-kodu → Task 5 (Step 3). ✓

**Placeholdery:** brak — wszystkie nagłówki RST, linki i ścieżki podane
dosłownie.

**Spójność nazw:** slugi w tabeli, nav (Task 9), index (Task 7) i CLAUDE.md
(Task 10) są identyczne (`deweloper/mapa-kodu.md` itd.).
