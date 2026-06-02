# Interaktywny eksplorator sieci współautorstwa (powiazania_autorow)

Data: 2026-06-02
Status: zaakceptowany (brainstorming) → do planu implementacji

## Cel

Udostępnić odwiedzającemu stronę autora interaktywną wizualizację sieci
współautorstwa. Start: ego-sieć danego autora („gwiazdka" — autor w centrum
+ jego bezpośredni współautorzy). Klik w dowolny węzeł **animowanie dorzuca**
współautorów tego węzła, więc sieć rozrasta się organicznie i daje się
eksplorować w głąb. Grubość krawędzi = liczba wspólnych publikacji.

## Stan obecny i decyzja

Aplikacja `src/powiazania_autorow/` ma **dobry fundament danych**, ale
**prototypową, źle zaprojektowaną warstwę wizualizacji**.

Zostaje (działa, jest przetestowane):
- `models.py` — `AuthorConnection` (para autorów `primary`/`secondary` z
  mniejszym ID jako `primary`, `shared_publications_count`, `unique_together`,
  indeksy).
- `core.py` — `calculate_author_connections()` (pełny przelicznik par
  współautorów z `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`,
  `Patent_Autor`).
- `tasks.py` — `calculate_author_connections_task`,
  `update_single_author_connections_task`.
- `tests.py` — testy modelu / core / tasków (importują wyłącznie `core`,
  `models`, `tasks` → bezpieczne przy usunięciu wizualizacji).
- migracje.

Do usunięcia (prototyp wizualizacji, generowanie JS f-stringiem, artefakty
buildu w gicie):
- `src/powiazania_autorow/visualization/` (cały pakiet: `__init__.py`,
  `data.py`, `html.py`, `js.py`).
- `src/powiazania_autorow/management/commands/generate_author_connections_viz.py`
  (jedyny konsument `visualization/`).
- `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.js`
  oraz `author_connections.html` (zacommitowane artefakty z katalogu wyjścia
  collectstatic).
- `src/bpp/static/bpp/js/visualizations/author-connections-ui.js`
  (zastąpiony nowym modułem).

## Architektura

Trzy luźno powiązane jednostki:

1. **Endpoint danych (JSON)** — bezstanowy, zwraca sąsiadów *dowolnego*
   autora. Ten sam endpoint obsługuje węzeł centralny i każde rozwinięcie.
2. **Statyczny moduł JS (Cytoscape.js + fcose)** — pobiera JSON, renderuje
   graf, obsługuje hover/klik/expand/suwak. Brak generowania kodu po stronie
   serwera.
3. **Podpięcie w `bpp`** — przycisk na stronie autora + dedykowana strona
   eksploratora.

### B. Endpoint danych

Nowy `powiazania_autorow/views.py` + `powiazania_autorow/urls.py`
(włączony w root `src/django_bpp/urls.py`, przed trasami autora z `bpp`,
choć kolizji nie ma dzięki dodatkowemu segmentowi ścieżki).

URL-e:
- `/autor/<int:pk>/powiazania/` → `GrafView` — renderuje stronę eksploratora.
- `/autor/<int:pk>/powiazania/dane.json` → `GrafDaneView` — dane JSON.

Kształt odpowiedzi JSON:
```json
{
  "center": {"id": 123, "label": "Jan Kowalski", "url": "/autor/jan-kowalski/"},
  "neighbors": [
    {"id": 456, "label": "Anna Nowak", "url": "/autor/anna-nowak/", "shared": 7}
  ]
}
```

Logika zapytania:
- `AuthorConnection.objects.filter(Q(primary_author_id=pk) | Q(secondary_author_id=pk))`.
- Wyznacz „tego drugiego" autora w parze; `select_related` na obu stronach.
- **Filtr widoczności: tylko sąsiedzi z `Autor.pokazuj=True`** (żeby ukryci
  autorzy nie wyciekali do publicznego grafu).
- Sortowanie malejąco po `shared_publications_count`.
- Twardy bezpiecznik payloadu: maks. 500 sąsiadów na odpowiedź (i tak suwak
  decyduje, ilu rysujemy; 500 to ochrona przed patologicznym payloadem).
- `label` = `"{imiona} {nazwisko}"`, `url` = `autor.get_absolute_url()`.

Widoczność węzła centralnego: zgodnie z obecnym zachowaniem `AutorView`
(`DetailView` bez filtra) — endpoint danych nie wymusza dodatkowych reguł na
centrum, ale **sąsiedzi zawsze filtrowani po `pokazuj=True`**.

### C. Harmonogram (celerybeat)

`calculate_author_connections` obecnie **nie jest** schedulowany → tabela
`AuthorConnection` się nie zapełnia. Dopisać do `CELERY_BEAT_SCHEDULE`
(`src/django_bpp/settings/base.py`) wpis odpalający
`powiazania_autorow.calculate_author_connections` raz na dobę
(np. `crontab(hour=4, minute=0)` — po istniejących nocnych taskach 3:00/3:30).

Poza zakresem (YAGNI): podpinanie `update_single_author_connections_task`
pod sygnały zapisu publikacji. Dzienny pełny recompute wystarcza; dane są
tanie. Można dodać później.

### D. Frontend — eksplorator (Cytoscape.js + fcose)

Szablon `src/powiazania_autorow/templates/powiazania_autorow/graf.html`:
- `{% extends "base.html" %}` (publiczny base, Foundation CSS).
- Prawie-pełnoekranowy `#cytoscape-container` (`data-autor-id`,
  `data-dane-url`).
- Panel kontrolny: suwak **top-N** (ile najsilniej powiązanych sąsiadów
  rysować na rozwinięcie / w widoku), przycisk reset widoku, legenda
  (grubość krawędzi = wspólne publikacje).
- Element tooltipa (hover) + panel info/nawigacji (gdy węzeł aktywny:
  nazwa, liczba wspólnych publikacji, przycisk „Przejdź do strony autora").
- Stan pusty: „Brak zarejestrowanych powiązań — dane przeliczane raz na dobę."

Statyczny moduł `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js`
(zwykły moduł, **bez** generowania przez serwer):
- Czyta `data-autor-id` / `data-dane-url` z kontenera.
- Fetch JSON centrum → budowa grafu Cytoscape, layout `fcose`.
- **Hover** węzła → tooltip (nazwa + liczba wspólnych publikacji).
- **Klik** węzła → fetch sąsiadów tego autora → animowane dodanie *nowych*
  węzłów/krawędzi (dedup po ID; jeśli węzeł/krawędź już są — nie duplikuj),
  ponowny `fcose` z `animate: true`, by sieć „dorastała".
- **Suwak top-N**: renderuje na żywo po stronie klienta (mało współautorów =
  wszyscy; dużo = top-N wg `shared`). Bez refetchu.
- Nawigacja do strony autora: przycisk w tooltipie/panelu (jawna, bez
  przypadkowych przeskoków podczas eksploracji).
- Obsługa błędu fetcha → komunikat w panelu.

Ładowanie biblioteki — **lazy, tylko na tej stronie** (nie w globalnym
`bundle.js`, zgodnie z kontraktem „bez CDN w runtime"):
- Dodać `cytoscape` + `cytoscape-fcose` do `package.json` (dependencies).
- Nowy entry `src/bpp/static/bpp/js/cytoscape-entry.js` importujący
  cytoscape + rejestrujący fcose, eksportujący do `window`.
- Drugi krok esbuild w `Gruntfile.js` (`shell:esbuildCytoscape`):
  `cytoscape-entry.js` → `src/bpp/static/bpp/js/dist/cytoscape-bundle.js`
  (`--bundle --format=iife --minify-*`), dołączony do taska `build`
  i `build-non-interactive`.
- `graf.html` dołącza `<script>` z `cytoscape-bundle.js` **oraz**
  `powiazania-autorow.js` tylko na tej stronie.

### E. Podpięcie na stronie autora

`src/bpp/templates/browse/autor.html`:
- Przycisk **„Zobacz sieć powiązań"** w sekcji akcji nagłówka, link do
  `/autor/<pk>/powiazania/`.
- Pokazywany tylko gdy autor ma powiązania.

`src/bpp/views/browse.py` (`AutorView.get_context_data`):
- Dorzucić tani `ma_powiazania = AuthorConnection.objects.filter(
  Q(primary_author=self.object) | Q(secondary_author=self.object)).exists()`.
- Import `AuthorConnection` z `powiazania_autorow.models` (bpp już zależy od
  tej apki w `INSTALLED_APPS`).

## Stany brzegowe

- Autor bez powiązań: przycisk ukryty; strona eksploratora (gdyby wejść
  wprost) pokazuje stan pusty.
- Błąd sieci przy fetchu danych: komunikat w panelu, graf nie znika.
- Węzeł rozwinięty ponownie: nie duplikuj węzłów/krawędzi (dedup po ID).
- Sąsiad z `pokazuj=False`: pominięty już po stronie endpointu.

## Testy

Backend (pytest, konwencje projektu — funkcje, `@pytest.mark.django_db`,
`model_bakery.baker`):
- `GrafDaneView`: sąsiedzi posortowani malejąco po `shared`.
- filtr `pokazuj=True` (sąsiad ukryty nie pojawia się w odpowiedzi).
- pusty wynik (autor bez powiązań) → `neighbors: []`.
- nieistniejący autor → 404.
- istniejące testy `tests.py` (model/core/tasks) pozostają zielone.

Frontend: test Playwright **pominięty** (decyzja użytkownika).

## Pliki

Tworzone:
- `src/powiazania_autorow/urls.py`
- `src/powiazania_autorow/templates/powiazania_autorow/graf.html`
- `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js`
- `src/bpp/static/bpp/js/cytoscape-entry.js`
- testy endpointu (rozszerzenie `src/powiazania_autorow/tests.py` lub nowy
  `test_views.py`)

Modyfikowane:
- `src/powiazania_autorow/views.py` (z pustego stuba)
- `src/django_bpp/urls.py` (include url-i apki)
- `src/django_bpp/settings/base.py` (`CELERY_BEAT_SCHEDULE`)
- `src/bpp/views/browse.py` (`AutorView.get_context_data`)
- `src/bpp/templates/browse/autor.html` (przycisk)
- `package.json` (cytoscape, cytoscape-fcose)
- `Gruntfile.js` (drugi entry esbuild + do tasków build)

Usuwane:
- `src/powiazania_autorow/visualization/` (cały katalog)
- `src/powiazania_autorow/management/commands/generate_author_connections_viz.py`
- `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.js`
- `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.html`
- `src/bpp/static/bpp/js/visualizations/author-connections-ui.js`

## Decyzje (z brainstormingu)

- Zakres: ego-sieć z progresywnym rozwijaniem on-click (nie globalny megagraf).
- Technologia: Cytoscape.js + fcose.
- Umiejscowienie: dedykowana strona + przycisk na stronie autora.
- Interakcja: hover = info, klik = rozwiń, nawigacja przyciskiem.
- Limit rozwijania: domyślny top-N + suwak w UI; mało współautorów = wszyscy.
- Dane: tanie (przeliczane w bazie); endpoint zwraca wszystkich sąsiadów,
  suwak top-N filtruje po stronie klienta.
- Playwright: pominięty.
