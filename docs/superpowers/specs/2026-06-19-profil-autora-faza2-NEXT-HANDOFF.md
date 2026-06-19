# Profil autora — STATUS po rewizji 2-kol + §3.8 + HANDOFF do następnej sesji

Data: 2026-06-19
Dotyczy: PR **#385** (branch `feature/profil-autora` → `dev`).
Poprzednie dokumenty (czytaj dla kontekstu, w tej kolejności):
1. `docs/superpowers/specs/2026-06-19-profil-autora-rewizja-2col-HANDOFF.md` (rewizja 2-kol)
2. `docs/superpowers/specs/2026-06-18-profil-autora-i-podstrona-design.md` (spec bazowy)

> Ten dokument jest samowystarczalny. Świeża sesja ma z niego wznowić bez
> dostępu do poprzednich rozmów.

## 0. Jak wznowić (środowisko)

- Worktree: `~/Programowanie/bpp-profil-autora`, branch `feature/profil-autora`.
  **NIE twórz nowego worktree, NIE pracuj w `~/Programowanie/bpp`.**
- HEAD na chwilę pisania: `bb37ebbba`. Working tree czysty.
- Push (SSH nie działa; gh zalogowany jako `mpasternak`):
  `git push https://github.com/iplweb/bpp.git feature/profil-autora:feature/profil-autora`
- Testy profilu: `PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest src/bpp/tests/test_profil/`
  - Gdy wyskoczy `bpp_uczelnia.site_id NOT NULL` (stale reuse-container) →
    `make clean-testcontainers` i odpal bez `REUSE` (świeży kontener OK).
- Czyste logiki (bez DB) szybciej: `PYTEST_TESTCONTAINERS_DISABLE=1 uv run pytest ...`
- Po zmianach SCSS: `grunt build` (skompilowany CSS jest poza gitem —
  commituj tylko źródła `.scss`).
- KAŻDY nowy `.py` (też migracje) → `uv run ruff format <plik>` przed commitem;
  `pre-commit` (bez argumentów) musi być zielony.

## 1. Co JEST zrobione (CI w pełni zielone na #385)

Cała **rewizja 2-kolumnowa §3.1–§3.7** + **self-service §3.8** wdrożone TDD,
commit po commicie. Wszystkie realne gejty zielone (Build test-runner image,
12 shardów Tests, Lint changed files, CodeQL, baseline freshness, vitest),
`mergeStateStatus: CLEAN`.

Commity tej linii pracy (najnowszy u góry):
- `bb37ebbba` test(fulltext): uniezależnienie testu od danych bazowych
- `353ccb20c` §3.8 self-service edycja biogramu i zdjęcia
- `92f0dd81b` fix CodeQL: stretched-link zamiast JS-nawigacji
- `76338b03a` fix CodeQL: bezpieczna nawigacja (zastąpione przez stretched-link)
- `f8049fd38` §3.1 admin (edytor układu na Uczelni) + SCSS 2-kol
- `06ebb1872` §3.7 historia zatrudnienia (lewa kolumna)
- `2a1ab948c` §3.6 klikalne statystyki wg charakteru → wyszukiwarka
- `065e394d7` §3.5 wykresy roczne (liniowy/słupkowy) + PK + IF
- `d5e3154b7` §3.4 klik w całą pozycję listy prac
- `8ab6c24a2` §3.1+§3.2+§3.3 układ per-Uczelnia + rejestr prawej kol + szablon 2-kol
- (Faza 1: `00264292e`, `65af2e00b`, `9951f7fb5`, `400f87d5c`, …)

### 1.1. Architektura — gdzie co jest
- Układ profilu = **globalny per-Uczelnia**: `Uczelnia.uklad_profilu_autora`
  (JSONField). `Autor.uklad_profilu` USUNIĘTE. Migracja `0445`.
- `bpp/profil_autora.py` — rejestr `KATALOG_SEKCJI` = **tylko PRAWA kolumna**
  (15 typów, bez `obowiazkowa`). `rozwiaz_uklad(uczelnia)`.
- `bpp/profil_autora_dane.py` — buildery + `przygotuj_sekcje(autor, uczelnia,
  request)`; helper `_agreguj_po_latach`. Nowe buildery `_wykres_pk_lata`,
  `_wykres_if_lata` (IF auto-hide gdy suma=0).
- `bpp/views/browse.py` `AutorView` — przekazuje `uczelnia` do `przygotuj_sekcje`;
  `BuildSearch.post` obsługuje `charakter_formalny` (przez
  `CharakterFormalnyQueryObject`, rozwiązuje po **nazwie**, nie pk).
- `bpp/templates/browse/autor.html` — 2 kolumny (Foundation grid w HTML):
  lewa `cell large-4` (stała: zdjęcie→biogram→jednostka→historia
  zatrudnienia→identyfikatory→metryki→stopnie→opis→cytowania→wyszukiwarka→
  raport), prawa `cell large-8` (pętla `sekcje_profilu`). Embed pełna szerokość
  pod gridem.
- Partiale sekcji: `browse/autor_sekcje/*.html`. Współdzielone:
  `_lista_prac.html` (stretched-link), `_wykres_lata.html` (liniowy>10 /
  słupkowy≤10), `_historia_zatrudnienia.html`.
- `Autor.historia_zatrudnienia()` — `bpp/models/autor.py`.
- Admin: edytor układu (JSON textarea) w `UczelniaAdmin` (fieldset „Profil
  autora (podstrona)"); `uklad_profilu` zniknęło z `AutorAdmin`.
- **§3.8 self-service**: `bpp/views/profil_edycja.py` (`ProfilEdycjaView`,
  `AutorProfilForm`, `WymagajAutoraMixin`, `ProfilBiogramPodgladView`); URL-e
  `bpp:profil-edycja`, `bpp:profil-biogram-podglad`; szablon
  `bpp/profil_edycja.html` (live preview, debounce, CSRF); link „Edytuj swoją
  stronę" na `bpp/profil_uzytkownika.html`. Autor edytuje TYLKO biogram+zdjęcie.
- Style: `bpp/static/scss/_autor-bem.scss` (2-kol, stretched-link + line-clamp,
  wykres liniowy SVG, statystyki-link, historia).
- Testy: `src/bpp/tests/test_profil/` (test_uklad, test_models, test_widok,
  test_lista_prac, test_wykresy, test_statystyki, test_historia, test_admin,
  test_profil_edycja, test_biogram, test_obrazy) — 60 zielonych (świeży kontener).

### 1.2. Lekcje / pułapki (żeby nie powtarzać)
- **CodeQL `js/xss-through-dom`**: zapis wartości z DOM do `window.location`
  jest sinkiem (możliwy `javascript:`). Dlatego klik w pozycję listy prac
  zrobiony jest jako **stretched-link** (pusta nakładka `<a>`), bez JS.
- **§3.6**: `CharakterFormalnyQueryObject.value_from_web` rozwiązuje po
  **`nazwa`** (MPTT z potomkami), NIE po pk. Formularz statystyk POST-uje
  `autor=<pk>` + `charakter_formalny=<nazwa>`.
- **pytest-split / shardy**: dodanie testów zmienia podział na shardy i może
  ujawnić testy zależne od danych bazowych, które poprzedzający test
  transakcyjny wyczyścił (`flush`). Każdy test musi deklarować WSZYSTKIE swoje
  zależności na danych referencyjnych (np. `typy_odpowiedzialnosci`).
- **CI**: realne gejty to `Build test-runner image` + `Tests (sharded)` (12
  shardów). Szybkie „success" <1 min = skip, nie dowód. Czytaj uważnie.

## 2. Świadomie ODŁOŻONE (decyzja użytkownika 2026-06-19)
- **`make baseline-update`** — NIE robić teraz. Do zrobienia **raz, przy
  scalaniu** (migracje 0444 + 0445; commit `baseline-sql/baseline.sql` +
  `baseline.meta.json`). NIE w równoległych branchach.
- **Scalenie / domknięcie PR #385** — nie teraz.

## 3. Co DALEJ (kandydaci na następną sesję; wybrać z użytkownikiem)

Kolejność = sugerowany priorytet. Każdy punkt to osobny, niezależny kawałek.

### 3.1. Wizualna weryfikacja strony (NISKI koszt, WYSOKA wartość) — REKOMENDOWANE NAJPIERW
Duża przebudowa UI poszła bez ani jednego spojrzenia w przeglądarkę.
- `uv run run-site run` (lub `--no-browser` w tle), wejść na `/bpp/autor/<pk>/`
  autora z publikacjami, zdjęciem, biogramem i historią zatrudnienia.
- Sprawdzić: 2 kolumny na desktopie i stackowanie na mobile; stretched-link
  (klik w pozycję działa, link DOI w opisie też); line-clamp opisu; wykres
  liniowy (>10 lat) vs słupkowy (≤10); klik w charakter → multiseek; embed pod
  gridem; `/profil/edycja/` (upload zdjęcia, live preview biogramu).
- Skalibrować wartości wstępne: próg „10 lat" wykresu, liczba linii line-clamp
  (teraz 3), szerokości kolumn. To było zaznaczone jako „do kalibracji
  wizualnej".

### 3.2. Edytor kafelkowy układu w `UczelniaAdmin` (drag-drop)
Teraz MVP = JSON w textarea (`uklad_profilu_autora`). Docelowo ładny UI:
lista sekcji z checkbox widoczności + select limitu + drag-drop kolejności,
serializacja do tego samego JSON-a. **Najpierw sprawdzić istniejący JS
sortowania w repo** (jest `sortable_field_name` w inline'ach adminów) zanim
dołożysz zależność. Reużyć `waliduj_uklad`/`KATALOG_SEKCJI` z `profil_autora.py`.

### 3.3. Eksport zbiorczy publikacji autora (BibTeX + RIS)
- BibTeX: reużycie `src/bpp/export/bibtex.py` (`export_to_bibtex`,
  `.to_bibtex()` na `.original`). Endpoint `/autor/<pk>/eksport.bib`.
- **RIS — net-new** (nie istnieje). Endpoint `/autor/<pk>/eksport.ris`.
- Świadomy limit/stream dla autorów z dużą liczbą prac.
- Sekcja `eksport` została USUNIĘTA z rejestru w rewizji — eksport wpiąć jako
  przyciski (lewa kolumna lub osobny blok), nie jako sekcję prawej kolumny.

### 3.4. Self-service: picker wyróżnionych prac (`WybranaPublikacjaAutora`)
Model + inline w adminie już są (Faza 1). Brakuje self-service: autor
dodaje/usuwa/sortuje wyróżnione prace (autocomplete) w `/profil/edycja/`.
Sekcja `wybrane_publikacje` w rejestrze jest domyślnie OFF — uczelnia może ją
włączyć w układzie.

### 3.5. Drobny polish (opcjonalnie)
- `_lista_prac.html`: `aria-label` nakładki jest generyczny („Szczegóły
  publikacji") — można wstawić tytuł pracy.
- `profil_edycja.html`: dodać help/skrót składni Markdown przy biogramie.
- Sprawdzić render `opis` vs `biogram` w lewej kolumnie (oba mogą być widoczne).

## 4. Reguły wykonania (z CLAUDE.md — trzymać się)
- TDD: test → patrz jak failuje → implementuj. Commit po commicie.
- Max 88 znaków (ruff). Komentarze django `{# #}` jedno-liniowe.
- Ikony: frontend publiczny → Foundation-Icons; admin → emoji.
- NIE nadpisywać klas grid Foundation w SCSS — zmieniać klasy w HTML.
- NIE edytować istniejących migracji. Nowa = `0446+`.
- `pre-commit` bez argumentów; fixy ręcznie (NIE `ruff --fix` batch).
