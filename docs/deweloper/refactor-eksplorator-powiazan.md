# Spec: refaktor eksploratora sieci powiązań (post-review)

Gałąź `powiazania-autorow-eksplorator`. Po self-review eksploratora
(`src/powiazania_autorow/` + `src/bpp/static/bpp/js/visualizations/`) do
zrobienia są trzy zmiany. **Każda musi zachować obecne zachowanie** —
funkcjonalność jest już ręcznie i testowo zweryfikowana (34 testy), to czysto
jakość/bezpieczeństwo, nie zmiana feature'ów.

## Zmiana 1 — rozbicie `powiazania-autorow.js` (1112 linii → moduły)

**Problem:** `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js` ma
1112 linii i ~106 funkcji w jednym IIFE (`init()`). Jedyny plik >600 linii.

**Podejście:** przenieść kod do bundla esbuild (jak `cytoscape-entry.js`) i
rozbić na moduły ES. Bundla NIE duplikujemy Cytoscape — viz wpinamy w istniejący
`cytoscape-entry.js`, który już ma cytoscape+fcose+svg.

**Build (istniejący):** `Gruntfile.js` → `shell:esbuildCytoscape` robi
`esbuild src/bpp/static/bpp/js/cytoscape-entry.js --bundle ... --outfile=
dist/cytoscape-bundle.js`. Z `--bundle` importy ES działają.

**Kroki:**
1. Utwórz katalog `src/bpp/static/bpp/js/powiazania/` z modułami ES (po jednym
   logicznym obszarze). Sugerowany podział (subagent może go dostroić, byle
   spójnie i każdy moduł <~250 linii):
   - `state.js` — fabryka kontekstu: tworzy i zwraca obiekt `ctx` z `cy`,
     cache'ami (`infoCache`, `neighborsCache`, `expanded`, `lastTree`), stanem
     (`topN`, `glebokosc`, `metryka`, `uklad`, `pokazWewn`, `progWewn`,
     `extraEdges`, `animujDodawanie`) i referencjami do elementów DOM.
   - `cy.js` — `utworzCy(container)` → instancja cytoscape + cała tablica stylów
     (włącznie z `.nowy`, `.wewnetrzna`, `.znaleziony`, `.powiazana-szukana`,
     `.przygaszony`).
   - `urls.js` — `daneUrl`, `siecUrl`, `zrodlaUrl`, `grafUrl`, `paramyFiltru`,
     `wybraneZrodla` (biorą `ctx`).
   - `sizing.js` — `wartoscMetryki`, `przeliczRozmiary`.
   - `dom.js` — `wyczysc`, `linkAkcja`.
   - `panel.js` — `pokazPanelAutora`, `pokazBlad`, `pokazTooltipAutor`,
     `pokazTooltipKrawedz`.
   - `search.js` — `szukaj`.
   - `group-edges.js` — `dodajKrawedzieWewn`, `usunKrawedzieWewn`,
     `konfigurujProgWewn`, `odswiezKrawedzieWewn`.
   - `layout.js` — `rozmiescWokol`, `pozycjeRadialne`, `pozycjeKoncentryczne`,
     `pozycjeUkladu`, `ulozGraf`.
   - `graph.js` — `dodajWezel`, `dodajKrawedz`, `dodajKrawedzProsta`,
     `renderujSiec`, `pokazSasiadow`, `rozwin`, `ustawZakresLat`.
   - `loaders.js` — `zaladujSiec`, `zaladujZrodla`, `dodajOptgroup`/
     `pozycjaZrodla`, `naglowekGrupyZrodel`, `filtrujListeZrodel`,
     `aktualizujLabelZrodla`.
   - `controls.js` — całe wiązanie zdarzeń (suwaki, szuflada źródeł, opcje
     zaawansowane, eksport PNG/SVG, odśwież, metryka, układ, rok, szukaj).
   - `index.js` — `init()`: odczyt datasetu kontenera, `utworzCy`, zbudowanie
     `ctx`, podpięcie zdarzeń, start (`zaladujZrodla()` + `zaladujSiec()`).
2. **Stan dzielony:** zamiast domknięcia, funkcje biorą `ctx` (lub
   destrukturyzują z niego `cy`/stan). Mutowalny stan żyje w `ctx`.
3. `cytoscape-entry.js`: po `cytoscape.use(...)` dodaj
   `import { init } from "./powiazania/index.js";` i odpal `init()` na
   `DOMContentLoaded` (lub od razu, jeśli DOM gotowy). Cytoscape przekaż przez
   `window.cytoscape` (jak teraz) albo importem do modułów — wybierz jedno
   i trzymaj się tego.
4. `graf.html`: usuń `<script src="…/visualizations/powiazania-autorow.js">`.
   Zostaje tylko `<script src="…/dist/cytoscape-bundle.js">`.
5. Usuń stary `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js`.
6. `grunt build` musi przejść bez błędów (esbuild zwaliduje importy). Brak
   zmian w zachowaniu UI.

**Zasady:** XSS-safe budowa DOM zostaje (`textContent`, nie `innerHTML`).
Wszystkie `catch` nadal logują (`console.error`)/pokazują błąd — żadnych pustych
catchy. Komentarze po polsku, max 88 kolumn nie obowiązuje JS, ale trzymaj
zwięźle.

## Zmiana 2 — `statement_timeout` na ścieżce z filtrem (backend)

**Problem:** przy aktywnym filtrze self-join `rekord__autorzy` na cache może być
ciężki dla gęstych sieci; jedyny bezpiecznik to `MAKS_GLEBOKOSC_FILTR=4`.

**Zmiana w `src/powiazania_autorow/views.py`:** owinąć zapytania liczone z cache
przy aktywnym filtrze w `SET LOCAL statement_timeout` (np. 8000 ms), żeby
patologiczny self-join ubił request zamiast męczyć bazę. Zaproponuj helper, np.:

```python
from contextlib import contextmanager
from django.db import connection, transaction

@contextmanager
def _limit_czasu(ms):
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL statement_timeout = %s", [ms])
        yield
```

Użyć go w `GrafPowiazanSiecView.get` (i `GrafPowiazanDaneView.get`) tylko gdy
`filtr.aktywny()`, obejmując liczenie BFS/sąsiadów. Złap `OperationalError`
(timeout) i zwróć czytelny JSON 503/`{"error": "..."}` zamiast 500. Stała na
górze pliku, np. `STATEMENT_TIMEOUT_FILTR_MS = 8000`.

## Zmiana 3 — token sekwencji żądań (frontend, race condition)

**Problem:** szybkie zmiany suwaków/filtrów odpalają kilka `fetch`-y; wolniejsza
wcześniejsza odpowiedź może nadpisać nowszy render (out-of-order).

**Zmiana:** w `loaders.js` (po refaktorze) / module ładowania utrzymuj rosnący
licznik `ctx.seq`. Każdy `zaladujSiec` zapamiętuje swój numer; render aplikuje
się tylko jeśli numer == bieżący `ctx.seq`. Analogicznie dla `zaladujZrodla`.
To kilka linii — ignoruj przestarzałe odpowiedzi.

## Zmiana 4 (drobna) — cap liczby źródeł/wydawców w filtrze

W `_filtr_z_request` (views.py) przytnij `zrodla`/`wydawcy` do np. 100 id, żeby
ktoś nie wysłał gigantycznego `IN`. Jedna linia per lista.

## Weryfikacja (po implementacji)

- Backend: `UV_NO_SYNC=1 uv run ruff check src/powiazania_autorow/` +
  `UV_NO_SYNC=1 uv run --all-extras pytest src/powiazania_autorow/ -n auto`
  (34 testy zielone). Dodaj test, że przy filtrze z `statement_timeout` happy
  path nadal działa.
- Frontend: `grunt build` przechodzi; `dist/cytoscape-bundle.js` powstaje.
  Smoke test w przeglądarce (orkiestrator zrobi): strona się ładuje bez błędów
  w konsoli, sieć się rysuje, filtr roku/źródła działa, eksport PNG/SVG, opcje
  zaawansowane się rozwijają.
