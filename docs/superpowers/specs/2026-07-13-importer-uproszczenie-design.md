# Uproszczenie importera publikacji (UI + bug Safari)

Data: 2026-07-13
Branch: `feat/importer-uproszczenie-kafelki`
Zakres: wyłącznie UI + jeden bugfix. Bez nowego providera (PubMed odłożony do
osobnego PR-a).

## Cel

Strona kafelkowa `importer_publikacji/` jest dobra, ale po kliknięciu kafla
trafiamy do współdzielonego formularza „Krok 1” z pełnym wyborem providerów
(radia) **oraz** listą sesji importu pod spodem. Chcemy: po kliknięciu kafla —
tylko pole na dane wybranego źródła, bez listy sesji. Plus kilka poprawek
kosmetycznych i naprawa martwej strony w Safari.

## A. Kafelek → tylko pole na dane

`IndexView._get_fetch_form` jest jedynym producentem `step_fetch.html` i **zawsze**
zna providera (`?provider=` z kafla albo deep-linku admina). `FetchView.post`
re-renderuje `step_fetch.html` przy błędzie walidacji. Zatem `step_fetch.html`
jest zawsze jedno-providerowy — upraszczamy go do tego wariantu:

- nagłówek: ikona + nazwa wybranego źródła,
- link **„← Wybierz inne źródło”** (przycisk normal) wracający do kafelków
  (breadcrumb „Importer publikacji” robi to samo),
- provider jako `<input type="hidden">` (nie `RadioSelect`),
- render **serwerowy tylko właściwego** pola dla trybu providera:
  - `InputMode.TEXT` (BibTeX) → `textarea` + „Importuj”,
  - `InputMode.IDENTIFIER` (CrossRef/PBN/DSpace/WWW) → jednowierszowe pole
    identyfikatora + „Pobierz dane”, label z `identifier_label`,
    help-text z `input_help_text`, placeholder z `input_placeholder`,
- **usuwamy** JS-owy toggle radio→pole (niepotrzebny — provider jest znany),
- **usuwamy** blok listy sesji (`{% if sessions is not None %}`) oraz
  `ctx.update(_sessions_list_context(request))` z `_get_fetch_form`.

### Zmiany

- `views/helpers.py`: `_fetch_context(form, request, provider_name)` zwraca
  metadane **jednego** providera (`provider_meta`) zamiast
  `providers_metadata_json` wszystkich. Nadal zwraca `form`.
- `views/wizard.py`:
  - `_get_fetch_form` — kontekst single-provider, bez `_sessions_list_context`.
  - `FetchView.post` — przy nie-validnym formularzu przekaż `provider_name`
    z `request.POST` do `_fetch_context`, żeby re-render był single-provider.
- `templates/.../partials/step_fetch.html` — przepisany na wariant
  jedno-providerowy (hidden provider + jedno pole + back-link, bez radia,
  bez listy sesji, bez toggle-JS).

Deep-linki admina (`?provider=X&identifier=Y`) nadal działają: identyfikator
jest pre-wypełniony, operator klika „Pobierz dane”.

## B. Układ kafelków 3+2

`.tile-grid--providers` w `src/bpp/static/scss/_wizard_forms.scss`: zamiast
`repeat(auto-fit, minmax(220px, 1fr))` — responsywne stałe kolumny:

- small (mobile): 1 kolumna,
- medium (≥640px): 2 kolumny,
- large (≥1024px): 3 kolumny.

5 kafelków → **3 + 2** na desktopie. Po zmianie: `grunt build`, commit
skompilowanego CSS.

## C. Przyciski nawigacyjne small/tiny → normal (tylko nawigacja)

Usuwamy `tiny`/`small` z przycisków **nawigacyjnych**:

- `step_landing.html` — „Importy w toku / ostatnie” (`button tiny secondary`),
- `session_list.html` — „Powrót do importera” (`button tiny secondary`),
- stopki kroków (`step_source.html`, `step_review.html`, `step_verify.html`,
  `step_authors.html`) — „Powrót do listy” (`button hollow secondary small`)
  i „Anuluj import” (`button alert hollow small`).

**Bez zmian (zostają tiny/small)** — inline'owe akcje w wierszach tabel oraz
kontrolki formularzy:

- `batch_detail.html` (Importuj/Pomiń/Kontynuuj/Ponów/Przywróć per wiersz),
- `author_row.html` (edycja/usuń autora), `_pbn_result_list.html`,
  `step_pbn.html`, „Kontynuuj” w `session_list.html`,
- „Reset” filtra w `session_list.html`,
- inline'owe `button small warning`/`small hollow` w krokach.

## D. Kolory statusów w liście sesji

Mapowanie klas Foundation przenosimy do testowalnej property
`ImportSession.status_badge_class` (zamiast drabiny `{% if %}` w szablonie):

| Status | Wyświetlane | Klasa | Kolor |
|---|---|---|---|
| `completed` | Zakończono | `success` | zielony (jedyny) |
| `import_failed` | Błąd importu | `alert` | czerwony |
| `fetching`, `creating` | Trwa pobieranie / tworzenie | `warning` | pomarańcz |
| `fetched`, `verified`, `source_matched`, `authors_matched`, `punktacja`, `pbn_check`, `review` | (w toku) | `secondary` | szary |

`cancelled` jest już wykluczony z listy. `session_list.html` używa
`{{ s.status_badge_class }}`.

## E. Bug Safari — martwa strona po htmx → wstecz

**Objaw:** po kilku interakcjach klik „Importy w toku” (nawigacja htmx),
potem Wstecz — w Safari błąd JS, strona nieklikalna.

**Hipoteza:** przy Back (bfcache / history-restore Safari) skrypt
`session_list.html` re-inicjalizuje DataTable/select2 →
`Cannot reinitialise DataTable` rzuca wyjątek → reszta handlera nie wykonuje
się → uchwyty zdarzeń niepodpięte → strona martwa.

**Fix (idempotentna inicjalizacja, dobra praktyka niezależnie od dokładnej
ścieżki):**

- DataTable: init tylko gdy `!$.fn.dataTable.isDataTable(table)`,
- select2: pomijaj elementy z klasą `.select2-hidden-accessible`
  (już zainicjalizowane),
- całość handlera w `try/catch` z `console.error` (BEZ cichego łykania —
  zgodnie z regułami repo: logujemy),
- utwardzenie re-inicjalizacji dla swapów htmx (init niezależny od
  pojedynczego `$(document).ready`, odporny na wielokrotne wywołanie).

**Weryfikacja:** użytkownik potwierdza w Safari po wdrożeniu; dodatkowo
(jeśli lokalnie zielone) test Playwright (Chromium): sessions → wstecz →
naprzód, DataTable dokładnie raz + znana kontrolka klikalna.

## Testy

- **Unit:** `ImportSession.status_badge_class` — każdy status → oczekiwana klasa.
- **Widok:** `_get_fetch_form` — kontekst ma `provider_meta`, **nie** ma
  `sessions`; `step_fetch` renderuje hidden `provider` + tylko właściwe pole,
  bez radia i bez tabeli sesji; deep-link prefill; `FetchView.post` invalid →
  re-render single-provider.
- **Regresja kolorów:** render listy sesji — `success` tylko dla `completed`,
  `warning` dla fetching/creating, `alert` dla import_failed, `secondary` dla
  reszty.
- **SCSS:** `grunt build` + sprawdzenie że skompilowany CSS się zmienił.
- **Playwright (opcjonalnie):** bug E.
- `make tests` (lub co najmniej moduł importera + szeroki przebieg).

## Dostarczane

- Worktree `~/Programowanie/bpp-importer-uproszczenie`,
  branch `feat/importer-uproszczenie-kafelki`.
- Newsfragmenty w `src/bpp/newsfragments/` (feature + bugfix).
- PR → `dev`.
