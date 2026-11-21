# Skrót `/` i nawigacja po grafie — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Domknąć kryteria WCAG 2.1.4 (mechanizm wyłączania skrótu `/`),
2.5.7 (nawigacja po grafie powiązań wskaźnikiem) i 2.1.1 (ta sama nawigacja
klawiaturą).

**Architecture:** Dwa niezależne moduły JS window-globalnych, wzorem
`related-records-highlight.js` z poprzedniej iteracji. Pierwszy trzyma
preferencję skrótów w `localStorage` i obsługuje przełącznik w stopce;
handlery `/` pytają go przed reakcją. Drugi wystawia czyste funkcje nad
instancją Cytoscape (`przesun`, `zoomuj`, `dopasuj`), z których korzystają
zarówno przyciski nakładki, jak i handler klawiatury.

**Tech Stack:** Django (szablony), JavaScript (moduły window-globalne, bez
bundlera dla `skroty-klawiszowe.js`; `nawigacja.js` idzie przez esbuild do
`cytoscape-bundle.js`), Cytoscape.js ^3.34.0, vitest, pytest, Playwright,
SCSS + grunt.

**Spec:** `docs/superpowers/specs/2026-08-07-wcag-skrot-i-graf-design.md`

## Global Constraints

- Wszystkie polecenia Pythona przez `uv run` — nigdy gołe `python`/`pytest`.
- Max długość linii Pythona: 88 znaków (ruff). JS i szablonów nie dotyczy.
- Testy: pytest, funkcje standalone (nie klasy), `@pytest.mark.django_db`
  gdzie potrzebna baza; `model_bakery.baker.make` do tworzenia obiektów.
- Testy JS: vitest, pliki w `tests/js/**/*.test.js`. Domyślne środowisko to
  `node` — plik testujący kod używający `window`/`localStorage` musi
  deklarować u siebie `// @vitest-environment jsdom`.
- Komentarze Django `{# … #}` **jednoliniowe** — każda linia własne
  otwarcie i zamknięcie. Wieloliniowy wycieka do wyrenderowanego HTML-a.
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`.
- `pre-commit` uruchamiać BEZ ARGUMENTÓW. Nigdy `--all-files`, nigdy
  `ruff check --fix` — problemy naprawiać ręcznie, po jednym.
- Na hoście mogą działać cudze kontenery testowe: NIE uruchamiać
  `make clean-testcontainers`.
- Praca w worktree `/Volumes/SSD/Programowanie/bpp-wcag-faza2`, gałąź
  `fix-wcag-2140-2570` (stacked na `fix-wcag-naprawy-stwierdzone`).
- Po zmianach SCSS: `grunt build` (albo `make assets`).

## Struktura plików

**Tworzone:**

| plik | odpowiedzialność |
|---|---|
| `src/bpp/static/bpp/js/skroty-klawiszowe.js` | preferencja skrótów + przełącznik |
| `tests/js/skroty-klawiszowe.test.js` | testy vitest modułu preferencji |
| `src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js` | czyste funkcje nawigacji nad Cytoscape |
| `tests/js/nawigacja-grafu.test.js` | testy vitest modułu nawigacji |
| `src/bpp/static/scss/graf_powiazan.scss` | nakładka nawigacji + pierścień focusa |
| `src/bpp/tests/test_wcag/test_skrot_szukania.py` | testy szablonowe części A |
| `src/powiazania_autorow/tests/__init__.py` | pakiet testów (jeśli nie istnieje) |
| `src/powiazania_autorow/tests/test_graf_dostepnosc.py` | testy szablonowe grafu |
| `src/integration_tests/test_wcag_skrot_i_graf.py` | testy Playwright |
| `src/bpp/newsfragments/wcag-skrot-i-graf.feature.rst` | newsfragment |

**Modyfikowane:**

| plik | zmiana |
|---|---|
| `src/django_bpp/templates/base.html:37-51` | **usunięcie** zduplikowanego handlera `/`; dodanie `<script src>` modułu |
| `src/django_bpp/templates/global_search_modal.html:1040-1052` | warunek preferencji w handlerze |
| `src/bpp/templates/browse/uczelnia.html:98-142` | warunek preferencji w handlerze banera i przy pokazywaniu banera |
| `src/django_bpp/templates/base_footer.html` | przycisk przełącznika |
| `src/powiazania_autorow/templates/powiazania_autorow/graf.html` | nakładka nawigacji; `tabindex`/`role`/`aria-label` na kontenerze |
| `src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js` | podpięcie przycisków i klawiatury |
| `src/bpp/static/scss/common.scss` | `@import "graf_powiazan";` |
| `docs/superpowers/specs/2026-08-06-…-design.md` | usunięcie 2.1.4 i 2.5.7 z wykazu odroczonych |
| `docs/superpowers/specs/2026-08-05-…-design.md` | jw. |

---

### Task 1: Moduł preferencji skrótów

**Files:**
- Create: `src/bpp/static/bpp/js/skroty-klawiszowe.js`
- Test: `tests/js/skroty-klawiszowe.test.js`

**Interfaces:**
- Consumes: nic
- Produces: trzy funkcje na `window`:
  - `bppSkrotyWlaczone()` → `boolean`
  - `bppUstawSkroty(wlaczone: boolean)` → `boolean` (nowy stan)
  - `bppPodepnijPrzelacznikSkrotow(el: HTMLElement)` → `void`

  Używane w Task 2 (szablony) i Task 6 (Playwright).

- [ ] **Step 1: Napisz testy vitest**

Utwórz `tests/js/skroty-klawiszowe.test.js`:

```javascript
// @vitest-environment jsdom
//
// Preferencja skrotow jednoznakowych (WCAG 2.1.4). Kryterium wymaga, zeby
// uzytkownik mogl skrot wylaczyc — BPP w czesci publicznej nie ma kont, wiec
// preferencja siedzi w localStorage. Domyslka to "wlaczone": brak wpisu nie
// moze zmieniac zachowania nikomu, kto nic nie ustawil.

import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const ZRODLO = readFileSync(
    resolve(__dirname, "../../src/bpp/static/bpp/js/skroty-klawiszowe.js"),
    "utf-8"
);

function zaladuj() {
    // Modul jest skryptem window-globalnym (IIFE), nie modulem ESM —
    // wykonujemy go na biezacym window jsdom.
    new Function(ZRODLO).call(window);
    return window;
}

beforeEach(() => {
    window.localStorage.clear();
    delete window.bppSkrotyWlaczone;
    delete window.bppUstawSkroty;
    delete window.bppPodepnijPrzelacznikSkrotow;
});

describe("bppSkrotyWlaczone", () => {
    it("domyslnie wlaczone gdy brak wpisu", () => {
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it('"0" wylacza', () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "0");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(false);
    });

    it('"1" wlacza', () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "1");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it("smiec w localStorage traktowany jak brak wpisu", () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "tak");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it("nie rzuca gdy localStorage niedostepny", () => {
        const oryginalny = window.localStorage.getItem;
        window.localStorage.getItem = () => {
            throw new Error("SecurityError");
        };
        const w = zaladuj();
        expect(w.bppSkrotyWlaczone()).toBe(true);
        window.localStorage.getItem = oryginalny;
    });
});

describe("bppUstawSkroty", () => {
    it("zapisuje wylaczenie i zwraca nowy stan", () => {
        const w = zaladuj();
        expect(w.bppUstawSkroty(false)).toBe(false);
        expect(window.localStorage.getItem("bpp.skrotyJednoznakowe")).toBe("0");
        expect(w.bppSkrotyWlaczone()).toBe(false);
    });

    it("zapisuje wlaczenie", () => {
        const w = zaladuj();
        w.bppUstawSkroty(false);
        expect(w.bppUstawSkroty(true)).toBe(true);
        expect(window.localStorage.getItem("bpp.skrotyJednoznakowe")).toBe("1");
    });

    it("nie rzuca gdy zapis niemozliwy", () => {
        const oryginalny = window.localStorage.setItem;
        window.localStorage.setItem = () => {
            throw new Error("QuotaExceededError");
        };
        const w = zaladuj();
        expect(() => w.bppUstawSkroty(false)).not.toThrow();
        window.localStorage.setItem = oryginalny;
    });
});

describe("bppPodepnijPrzelacznikSkrotow", () => {
    function przycisk() {
        const el = window.document.createElement("button");
        window.document.body.appendChild(el);
        return el;
    }

    it("ustawia stan poczatkowy na wlaczony", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        expect(el.getAttribute("aria-pressed")).toBe("true");
        expect(el.textContent).toContain("włączone");
    });

    it("klik wylacza skroty i aktualizuje etykiete", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        el.click();
        expect(w.bppSkrotyWlaczone()).toBe(false);
        expect(el.getAttribute("aria-pressed")).toBe("false");
        expect(el.textContent).toContain("wyłączone");
    });

    it("drugi klik wraca do stanu wyjsciowego", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        el.click();
        el.click();
        expect(w.bppSkrotyWlaczone()).toBe(true);
        expect(el.getAttribute("aria-pressed")).toBe("true");
    });

    it("odzwierciedla stan zapisany wczesniej", () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "0");
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        expect(el.getAttribute("aria-pressed")).toBe("false");
    });
});
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-faza2
npx vitest run tests/js/skroty-klawiszowe.test.js
```

Oczekiwane: FAIL — brak pliku `skroty-klawiszowe.js`.

- [ ] **Step 3: Napisz moduł**

Utwórz `src/bpp/static/bpp/js/skroty-klawiszowe.js`:

```javascript
/**
 * Preferencja skrotow jednoznakowych (WCAG 2.1.4 Character Key Shortcuts).
 *
 * Kryterium wymaga, zeby skrot zlozony z samych znakow drukowalnych dalo sie
 * wylaczyc, przemapowac albo ograniczyc do focusa komponentu. Skrot `/`
 * otwierajacy wyszukiwarke globalna wisi na `document`, wiec wybieramy
 * pierwsza droge.
 *
 * BPP w czesci publicznej nie ma kont uzytkownikow (GitHub i Gmail trzymaja
 * taka preferencje w profilu), wiec zapisujemy ja w localStorage. Kryterium
 * nie wymaga trwalosci miedzy urzadzeniami — tylko istnienia mechanizmu.
 *
 * Domyslka: WLACZONE. Brak wpisu nie moze zmieniac zachowania nikomu, kto
 * nic nie ustawil.
 */
(function (window) {
    "use strict";

    var KLUCZ = "bpp.skrotyJednoznakowe";
    var ETYKIETA_WL = "Skróty klawiszowe: włączone";
    var ETYKIETA_WYL = "Skróty klawiszowe: wyłączone";

    function bppSkrotyWlaczone() {
        try {
            return window.localStorage.getItem(KLUCZ) !== "0";
        } catch (e) {
            // Tryb prywatny, wylaczone ciasteczka, wyczerpany limit —
            // degradujemy do domyslki zamiast wywracac obsluge klawisza.
            return true;
        }
    }

    function bppUstawSkroty(wlaczone) {
        try {
            window.localStorage.setItem(KLUCZ, wlaczone ? "1" : "0");
        } catch (e) {
            // Zapis niemozliwy — preferencja nie przetrwa przeladowania,
            // ale biezaca sesja i tak dziala na zwroconej wartosci.
        }
        return !!wlaczone;
    }

    function bppPodepnijPrzelacznikSkrotow(el) {
        if (!el) {
            return;
        }

        function odswiez() {
            var wl = bppSkrotyWlaczone();
            el.setAttribute("aria-pressed", wl ? "true" : "false");
            el.textContent = wl ? ETYKIETA_WL : ETYKIETA_WYL;
        }

        el.addEventListener("click", function () {
            bppUstawSkroty(!bppSkrotyWlaczone());
            odswiez();
        });

        odswiez();
    }

    window.bppSkrotyWlaczone = bppSkrotyWlaczone;
    window.bppUstawSkroty = bppUstawSkroty;
    window.bppPodepnijPrzelacznikSkrotow = bppPodepnijPrzelacznikSkrotow;
})(typeof window !== "undefined" ? window : this);
```

- [ ] **Step 4: Uruchom testy — muszą przejść**

```bash
npx vitest run tests/js/skroty-klawiszowe.test.js
```

Oczekiwane: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/static/bpp/js/skroty-klawiszowe.js \
    tests/js/skroty-klawiszowe.test.js
git commit -m "feat(wcag): modul preferencji skrotow jednoznakowych (2.1.4)"
```

---

### Task 2: Podpięcie preferencji do wszystkich handlerów `/`

Skrót obsługiwany jest w trzech publicznych miejscach. Objęcie warunkiem
jednego nie da nic — pozostałe zareagują niezależnie.

**Files:**
- Modify: `src/django_bpp/templates/base.html:19` (dodanie `<script src>`), `:37-51` (usunięcie handlera)
- Modify: `src/django_bpp/templates/global_search_modal.html:1040-1052`
- Modify: `src/bpp/templates/browse/uczelnia.html:96-142`
- Modify: `src/django_bpp/templates/base_footer.html`
- Test: `src/bpp/tests/test_wcag/test_skrot_szukania.py`

**Interfaces:**
- Consumes: `window.bppSkrotyWlaczone()`, `window.bppPodepnijPrzelacznikSkrotow(el)` z Task 1
- Produces: przycisk `#bpp-przelacznik-skrotow` w stopce (używany w Task 6)

- [ ] **Step 1: Napisz testy szablonowe**

Utwórz `src/bpp/tests/test_wcag/test_skrot_szukania.py`:

```python
"""WCAG 2.1.4 — mechanizm wyłączania skrótu `/`.

Skrót obsługiwany był w trzech publicznych miejscach naraz; dwa z nich
(`base.html` i `global_search_modal.html`) otwierały wyszukiwarkę
niezależnie, więc na jedno naciśnięcie `openGlobalSearch` wołane było
dwukrotnie. Duplikat zlikwidowano — zostaje handler w modalu.

Testy pilnują trzech rzeczy: modułu preferencji faktycznie podpiętego,
przełącznika w stopce oraz braku powrotu usuniętego handlera.
"""

from pathlib import Path

import pytest
from django.template.loader import render_to_string

SZABLONY = Path(__file__).resolve().parents[3] / "django_bpp" / "templates"


def _tresc(nazwa):
    return (SZABLONY / nazwa).read_text(encoding="utf-8")


def test_modul_skrotow_podpiety_w_base():
    # Bez tego tagu przełącznik i warunki w handlerach przestają działać,
    # a żaden inny test by tego nie wykrył.
    assert "skroty-klawiszowe.js" in _tresc("base.html")


def test_base_nie_ma_juz_wlasnego_handlera_skrotu():
    # Dowód likwidacji duplikatu: handler żyje wyłącznie w modalu.
    tresc = _tresc("base.html")
    assert "e.key === '/'" not in tresc


def test_modal_pyta_o_preferencje():
    tresc = _tresc("global_search_modal.html")
    assert "e.key === '/'" in tresc
    assert "bppSkrotyWlaczone" in tresc


def test_modal_ma_guard_typeof():
    # Gdy moduł się nie załaduje, gołe wywołanie rzucałoby TypeError przy
    # każdym naciśnięciu `/` i skrót umarłby po cichu.
    assert "typeof window.bppSkrotyWlaczone" in _tresc("global_search_modal.html")


@pytest.mark.django_db
def test_stopka_ma_przelacznik(client):
    html = render_to_string("base_footer.html", {})

    assert 'id="bpp-przelacznik-skrotow"' in html
    assert 'aria-pressed' in html
    assert 'type="button"' in html
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_skrot_szukania.py -v
```

Oczekiwane: FAIL na wszystkich poza `test_modal_pyta_o_preferencje`
(częściowo — `e.key === '/'` już tam jest, `bppSkrotyWlaczone` jeszcze nie).

- [ ] **Step 3: Dodaj `<script src>` modułu w `base.html`**

W `src/django_bpp/templates/base.html`, obok istniejącego tagu w linii 19
(`formdefaults/modal.js`), dopisz:

```django
        <script src="{% static 'bpp/js/skroty-klawiszowe.js' %}"></script>
```

Bez `defer` — moduł musi być dostępny, gdy handlery sprawdzają preferencję
przy naciśnięciu klawisza, a przełącznik w stopce podpina się po
`DOMContentLoaded`.

- [ ] **Step 4: Usuń zduplikowany handler z `base.html`**

W `src/django_bpp/templates/base.html` usuń CAŁY blok (linie 37-51):

```django
    <script type="text/javascript">
        // Global search hotkey handler
        document.addEventListener('DOMContentLoaded', function() {
            document.addEventListener('keydown', function(e) {
                // Check if "/" key is pressed and not in an input field
                if (e.key === '/' && !$(e.target).is('input, textarea, select')) {
                    e.preventDefault(); // Prevent default search behavior
                    if (typeof openGlobalSearch === 'function') {
                        openGlobalSearch(null, true); // Pass true to indicate keyboard trigger
                    }
                }
            });
        });
    </script>
```

Handler w `global_search_modal.html` robi to samo i dodatkowo sprawdza stan
modala. Zostawienie obu oznacza dwa wywołania `openGlobalSearch` na jedno
naciśnięcie klawisza.

- [ ] **Step 5: Dodaj warunek w `global_search_modal.html`**

W `src/django_bpp/templates/global_search_modal.html`, linie 1047-1052,
zamień:

```javascript
            // Check for "/" key (forward slash)
            if (e.key === '/' && !$('#globalSearchModal').hasClass('show')) {
                e.preventDefault();
                openGlobalSearch(null, true); // Pass true to indicate keyboard trigger
            }
```

na:

```javascript
            // Check for "/" key (forward slash)
            // WCAG 2.1.4: skrot jednoznakowy musi dac sie wylaczyc.
            // Guard `typeof` — gdy modul sie nie zaladuje, degradujemy do
            // zachowania dotychczasowego zamiast rzucac TypeError.
            var skrotyWl = (typeof window.bppSkrotyWlaczone !== 'function'
                            || window.bppSkrotyWlaczone());
            if (e.key === '/' && skrotyWl
                && !$('#globalSearchModal').hasClass('show')) {
                e.preventDefault();
                openGlobalSearch(null, true); // Pass true to indicate keyboard trigger
            }
```

- [ ] **Step 6: Dodaj warunek w `browse/uczelnia.html`**

Dwie zmiany w `src/bpp/templates/browse/uczelnia.html`.

Pierwsza — handler zamykający baner (linie 134-141), zamień:

```javascript
    document.addEventListener('keydown', function(e) {
        if (e.key === '/' && !$(e.target).is('input, textarea, select')) {
```

na:

```javascript
    document.addEventListener('keydown', function(e) {
        var skrotyWl = (typeof window.bppSkrotyWlaczone !== 'function'
                        || window.bppSkrotyWlaczone());
        if (e.key === '/' && skrotyWl && !$(e.target).is('input, textarea, select')) {
```

Druga — pokazywanie banera (linie 102-108). Baner reklamuje skrót
(„Wciśnij klawisz `/`…"), więc przy wyłączonych skrótach nie może się
pojawiać. Zamień:

```javascript
        if (!bannerDismissed || (dismissedDate && daysSince(dismissedDate) > 30)) {
```

na:

```javascript
        // WCAG 2.1.4: nie reklamuj skrotu, ktory uzytkownik wylaczyl.
        var skrotyWl = (typeof window.bppSkrotyWlaczone !== 'function'
                        || window.bppSkrotyWlaczone());
        if (skrotyWl
            && (!bannerDismissed || (dismissedDate && daysSince(dismissedDate) > 30))) {
```

- [ ] **Step 7: Dodaj przycisk w stopce**

W `src/django_bpp/templates/base_footer.html`, wewnątrz
`<div class="footer__content">`, przed blokiem
`{% if uczelnia.pokazuj_deklaracje_dostepnosci == 1 %}`, dodaj:

```django
            {# WCAG 2.1.4: mechanizm wylaczenia skrotow jednoznakowych. #}
            {# Stopka, bo strona deklaracji dostepnosci jest opcjonalna #}
            {# (Uczelnia.pokazuj_deklaracje_dostepnosci) i bywa zewnetrzna. #}
            <button type="button" id="bpp-przelacznik-skrotow"
                    class="footer__link-button" aria-pressed="true">Skróty klawiszowe: włączone</button> |
```

Na końcu pliku dodaj podpięcie:

```django
<script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function () {
        if (typeof window.bppPodepnijPrzelacznikSkrotow === 'function') {
            window.bppPodepnijPrzelacznikSkrotow(
                document.getElementById('bpp-przelacznik-skrotow')
            );
        }
    });
</script>
```

- [ ] **Step 8: Dodaj styl przycisku**

Przycisk ma wyglądać jak sąsiednie linki stopki, nie jak przycisk
formularza. W `src/bpp/static/scss/base_footer.scss` (bez podkreślnika —
tak nazywa się w tym projekcie, mimo że część partiali ma prefiks) dopisz:

```scss
// Przelacznik skrotow klawiszowych (WCAG 2.1.4) ma wygladac jak sasiednie
// linki stopki — jest <button>, bo zmienia stan aplikacji, a nie nawiguje.
.footer__link-button {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    font: inherit;
    color: inherit;
    text-decoration: underline;
    cursor: pointer;
}
```

Jeżeli plik nazywa się inaczej, sprawdź:
`ls src/bpp/static/scss/ | grep -i footer`.

Następnie przebuduj CSS:

```bash
grunt build
```

- [ ] **Step 9: Uruchom testy — muszą przejść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_skrot_szukania.py -v
npx vitest run tests/js/skroty-klawiszowe.test.js
```

Oczekiwane: 5 passed (pytest), 13 passed (vitest).

- [ ] **Step 10: Regresja szablonów**

```bash
uv run pytest src/bpp/tests/test_views/ -q
```

Oczekiwane: bez nowych błędów.

- [ ] **Step 11: Commit**

```bash
git add src/django_bpp/templates/base.html \
    src/django_bpp/templates/global_search_modal.html \
    src/bpp/templates/browse/uczelnia.html \
    src/django_bpp/templates/base_footer.html \
    src/bpp/static/scss/ \
    src/bpp/tests/test_wcag/test_skrot_szukania.py
git commit -m "feat(wcag): przelacznik skrotow w stopce, likwidacja duplikatu handlera (2.1.4)"
```

---

### Task 3: Moduł nawigacji po grafie

**Files:**
- Create: `src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js`
- Test: `tests/js/nawigacja-grafu.test.js`

**Interfaces:**
- Consumes: nic
- Produces: moduł ESM eksportujący:
  - `przesun(cy, kierunek)` — `kierunek` ∈ `"gora" | "dol" | "lewo" | "prawo"`
  - `zoomuj(cy, wspolczynnik)` — `wspolczynnik` > 1 przybliża, < 1 oddala
  - `dopasuj(cy)`

  Importowane w Task 4 (przyciski) i Task 5 (klawiatura).

- [ ] **Step 1: Napisz testy vitest**

Utwórz `tests/js/nawigacja-grafu.test.js`:

```javascript
// Nawigacja po grafie powiazan bez przeciagania (WCAG 2.5.7) i z klawiatury
// (2.1.1). Modul operuje na instancji Cytoscape przez jej publiczne API,
// wiec testujemy go na atrapie — bez uruchamiania biblioteki.

import { describe, it, expect, beforeEach } from "vitest";
import {
    przesun,
    zoomuj,
    dopasuj
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js";

function atrapaCy(opcje) {
    opcje = opcje || {};
    const stan = {
        panBy: null,
        zoomArg: null,
        fitWolane: false,
        poziomZoom: opcje.zoom === undefined ? 1 : opcje.zoom
    };
    return {
        _stan: stan,
        width: () => (opcje.width === undefined ? 1000 : opcje.width),
        height: () => (opcje.height === undefined ? 500 : opcje.height),
        minZoom: () => 0.1,
        maxZoom: () => 4,
        zoom: function (arg) {
            if (arg === undefined) {
                return stan.poziomZoom;
            }
            stan.zoomArg = arg;
            stan.poziomZoom = arg.level;
            return undefined;
        },
        panBy: function (arg) {
            stan.panBy = arg;
        },
        fit: function () {
            stan.fitWolane = true;
        }
    };
}

describe("przesun", () => {
    let cy;
    beforeEach(() => {
        cy = atrapaCy();
    });

    it("w prawo przesuwa widok w lewo (ujemny x)", () => {
        przesun(cy, "prawo");
        expect(cy._stan.panBy.x).toBeLessThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });

    it("w lewo przesuwa widok w prawo (dodatni x)", () => {
        przesun(cy, "lewo");
        expect(cy._stan.panBy.x).toBeGreaterThan(0);
        expect(cy._stan.panBy.y).toBe(0);
    });

    it("w dol przesuwa widok w gore (ujemny y)", () => {
        przesun(cy, "dol");
        expect(cy._stan.panBy.y).toBeLessThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("w gore przesuwa widok w dol (dodatni y)", () => {
        przesun(cy, "gora");
        expect(cy._stan.panBy.y).toBeGreaterThan(0);
        expect(cy._stan.panBy.x).toBe(0);
    });

    it("krok skaluje sie z szerokoscia widoku", () => {
        const waski = atrapaCy({ width: 500 });
        const szeroki = atrapaCy({ width: 2000 });
        przesun(waski, "prawo");
        przesun(szeroki, "prawo");
        expect(Math.abs(szeroki._stan.panBy.x)).toBeGreaterThan(
            Math.abs(waski._stan.panBy.x)
        );
    });

    it("nieznany kierunek nic nie robi", () => {
        przesun(cy, "wszedzie");
        expect(cy._stan.panBy).toBeNull();
    });
});

describe("zoomuj", () => {
    it("przyblizanie zwieksza poziom", () => {
        const cy = atrapaCy({ zoom: 1 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.level).toBeCloseTo(1.2);
    });

    it("oddalanie zmniejsza poziom", () => {
        const cy = atrapaCy({ zoom: 1 });
        zoomuj(cy, 1 / 1.2);
        expect(cy._stan.zoomArg.level).toBeLessThan(1);
    });

    it("nie przekracza maxZoom", () => {
        const cy = atrapaCy({ zoom: 3.9 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.level).toBe(4);
    });

    it("nie schodzi ponizej minZoom", () => {
        const cy = atrapaCy({ zoom: 0.11 });
        zoomuj(cy, 1 / 1.2);
        expect(cy._stan.zoomArg.level).toBe(0.1);
    });

    it("zoomuje wokol srodka widoku", () => {
        const cy = atrapaCy({ width: 1000, height: 500 });
        zoomuj(cy, 1.2);
        expect(cy._stan.zoomArg.renderedPosition).toEqual({ x: 500, y: 250 });
    });
});

describe("dopasuj", () => {
    it("wola cy.fit()", () => {
        const cy = atrapaCy();
        dopasuj(cy);
        expect(cy._stan.fitWolane).toBe(true);
    });
});
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
npx vitest run tests/js/nawigacja-grafu.test.js
```

Oczekiwane: FAIL — brak pliku `nawigacja.js`.

- [ ] **Step 3: Napisz moduł**

Utwórz
`src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js`:

```javascript
// Nawigacja po grafie bez przeciagania (WCAG 2.5.7 Dragging Movements) oraz
// z klawiatury (2.1.1 Keyboard). Kryterium 2.5.7 wymaga, zeby funkcje
// dostepna przez przeciaganie dalo sie wykonac pojedynczym wskaznikiem —
// stad przyciski. Te same funkcje obsluguja klawiature.
//
// Modul operuje wylacznie na publicznym API Cytoscape, wiec da sie go
// przetestowac na atrapie, bez uruchamiania biblioteki.

// Krok przesuniecia jako UDZIAL rozmiaru widoku, nie stala w pikselach:
// przy duzym przyblizeniu stala byla by ledwo zauwazalna, przy oddaleniu
// przeskakiwala by caly graf.
const UDZIAL_KROKU = 0.2;

export function przesun(cy, kierunek) {
    const dx = cy.width() * UDZIAL_KROKU;
    const dy = cy.height() * UDZIAL_KROKU;

    // Znaki sa odwrocone wzgledem intuicji: `panBy` przesuwa PLOTNO,
    // a przyciski opisuja ruch WIDOKU. "w prawo" = plotno w lewo.
    switch (kierunek) {
        case "prawo":
            cy.panBy({ x: -dx, y: 0 });
            break;
        case "lewo":
            cy.panBy({ x: dx, y: 0 });
            break;
        case "dol":
            cy.panBy({ x: 0, y: -dy });
            break;
        case "gora":
            cy.panBy({ x: 0, y: dy });
            break;
        default:
            break;
    }
}

export function zoomuj(cy, wspolczynnik) {
    // Limity czytamy z instancji (utworzCy ustawia minZoom 0.1, maxZoom 4),
    // zeby nie duplikowac ich w dwoch miejscach.
    const docelowy = Math.min(
        Math.max(cy.zoom() * wspolczynnik, cy.minZoom()),
        cy.maxZoom()
    );

    cy.zoom({
        level: docelowy,
        renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
    });
}

export function dopasuj(cy) {
    cy.fit();
}
```

- [ ] **Step 4: Uruchom testy — muszą przejść**

```bash
npx vitest run tests/js/nawigacja-grafu.test.js
```

Oczekiwane: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js \
    tests/js/nawigacja-grafu.test.js
git commit -m "feat(wcag): modul nawigacji po grafie powiazan (2.5.7)"
```

---

### Task 4: Przyciski nawigacji w grafie

**Files:**
- Modify: `src/powiazania_autorow/templates/powiazania_autorow/graf.html` (nakładka przed `</div>` zamykającym `#graf-wrapper`)
- Modify: `src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js`
- Create: `src/bpp/static/scss/graf_powiazan.scss`
- Modify: `src/bpp/static/scss/common.scss`
- Create: `src/powiazania_autorow/tests/__init__.py` (jeśli nie istnieje)
- Test: `src/powiazania_autorow/tests/test_graf_dostepnosc.py`

**Interfaces:**
- Consumes: `przesun`, `zoomuj`, `dopasuj` z Task 3
- Produces: siedem przycisków o identyfikatorach `graf-nav-gora`,
  `graf-nav-dol`, `graf-nav-lewo`, `graf-nav-prawo`, `graf-nav-zoom-in`,
  `graf-nav-zoom-out`, `graf-nav-dopasuj` (używane w Task 6)

- [ ] **Step 1: Sprawdź, czy pakiet testów istnieje**

```bash
ls src/powiazania_autorow/tests/__init__.py 2>/dev/null \
  || (mkdir -p src/powiazania_autorow/tests && touch src/powiazania_autorow/tests/__init__.py)
```

Uwaga: istniejące testy tej aplikacji leżą płasko
(`src/powiazania_autorow/test_views.py`), ale nowy plik dotyczy dostępności i
zyskuje na wydzieleniu.

- [ ] **Step 2: Napisz testy szablonowe**

Utwórz `src/powiazania_autorow/tests/test_graf_dostepnosc.py`:

```python
"""Dostępność grafu powiązań: nawigacja wskaźnikiem (2.5.7) i klawiaturą (2.1.1).

Graf stoi na Cytoscape.js i do tej pory dawał się przesuwać wyłącznie
przeciąganiem. Kryterium 2.5.7 wymaga alternatywy realizowanej pojedynczym
wskaźnikiem — stąd przyciski. Sam kontener zyskuje `tabindex`, żeby te same
funkcje dało się wywołać z klawiatury (2.1.1).
"""

from pathlib import Path

SZABLON = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "powiazania_autorow"
    / "graf.html"
)

PRZYCISKI = [
    "graf-nav-gora",
    "graf-nav-dol",
    "graf-nav-lewo",
    "graf-nav-prawo",
    "graf-nav-zoom-in",
    "graf-nav-zoom-out",
    "graf-nav-dopasuj",
]


def _tresc():
    return SZABLON.read_text(encoding="utf-8")


def test_wszystkie_przyciski_nawigacji_obecne():
    tresc = _tresc()
    for identyfikator in PRZYCISKI:
        assert f'id="{identyfikator}"' in tresc, f"brak przycisku {identyfikator}"


def test_kazdy_przycisk_ma_aria_label():
    # Sam glif strzałki nic nie mówi czytnikowi ekranu.
    tresc = _tresc()
    fragmenty = tresc.split("<button")
    nawigacyjne = [f for f in fragmenty if "graf-nav-" in f]

    assert len(nawigacyjne) == len(PRZYCISKI)
    for fragment in nawigacyjne:
        assert "aria-label=" in fragment


def test_przyciski_sa_typu_button():
    # Bez type="button" przycisk wewnątrz formularza wysyła go.
    tresc = _tresc()
    for fragment in tresc.split("<button")[1:]:
        if "graf-nav-" in fragment:
            assert 'type="button"' in fragment


def test_glify_ukryte_przed_czytnikiem():
    # Treść dla czytnika jest w aria-label; glif to dekoracja.
    tresc = _tresc()
    for fragment in tresc.split("<button")[1:]:
        if "graf-nav-" in fragment:
            assert 'aria-hidden="true"' in fragment
```

- [ ] **Step 3: Uruchom testy — muszą paść**

```bash
uv run pytest src/powiazania_autorow/tests/test_graf_dostepnosc.py -v
```

Oczekiwane: FAIL — brak przycisków w szablonie.

- [ ] **Step 4: Dodaj nakładkę do `graf.html`**

W `src/powiazania_autorow/templates/powiazania_autorow/graf.html`, wewnątrz
`#graf-wrapper`, bezpośrednio po bloku `#graf-notka` (kończącym się w linii
199) a przed `</div>` zamykającym wrapper, wstaw:

```django
        {# WCAG 2.5.7: nawigacja bez przeciagania. Prawy dolny rog to #}
        {# jedyny wolny — lewy gorny zajmuje #graf-panel, prawy gorny #}
        {# #graf-legenda, lewy dolny #graf-notka (przy przycietej sieci). #}
        <div id="graf-nawigacja" class="graf-nawigacja">
            <button type="button" id="graf-nav-gora" class="graf-nawigacja__btn"
                    aria-label="Przesuń widok w górę"><span aria-hidden="true">↑</span></button>
            <button type="button" id="graf-nav-lewo" class="graf-nawigacja__btn"
                    aria-label="Przesuń widok w lewo"><span aria-hidden="true">←</span></button>
            <button type="button" id="graf-nav-dopasuj" class="graf-nawigacja__btn"
                    aria-label="Dopasuj graf do ekranu"><span aria-hidden="true">⤢</span></button>
            <button type="button" id="graf-nav-prawo" class="graf-nawigacja__btn"
                    aria-label="Przesuń widok w prawo"><span aria-hidden="true">→</span></button>
            <button type="button" id="graf-nav-dol" class="graf-nawigacja__btn"
                    aria-label="Przesuń widok w dół"><span aria-hidden="true">↓</span></button>
            <button type="button" id="graf-nav-zoom-in" class="graf-nawigacja__btn"
                    aria-label="Przybliż"><span aria-hidden="true">+</span></button>
            <button type="button" id="graf-nav-zoom-out" class="graf-nawigacja__btn"
                    aria-label="Oddal"><span aria-hidden="true">−</span></button>
        </div>
```

- [ ] **Step 5: Utwórz partial SCSS**

Utwórz `src/bpp/static/scss/graf_powiazan.scss`:

```scss
// Nakladka nawigacji po grafie powiazan (WCAG 2.5.7) oraz pierscien focusa
// kontenera grafu (2.4.7). Aplikacja powiazania_autorow nie ma wlasnego
// katalogu SCSS — graf.html opisuje wyglad atrybutami style="" — ale
// :focus-visible wymaga arkusza, wiec komponent siedzi w calosci tutaj.

.graf-nawigacja {
    position: absolute;
    right: 10px;
    bottom: 10px;
    z-index: 1001;

    display: grid;
    grid-template-columns: repeat(3, auto);
    gap: 2px;

    padding: 6px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #ddd;
    border-radius: 4px;
}

.graf-nawigacja__btn {
    // WCAG 2.5.8 (Target Size Minimum): cel dotykowy nie mniejszy niz
    // 24x24 px CSS. Naprawiajac 2.5.7 nie wolno zlamac sasiedniego
    // kryterium.
    min-width: 28px;
    min-height: 28px;

    padding: 0;
    margin: 0;
    font-size: 15px;
    line-height: 1;

    background: #fff;
    border: 1px solid #ccc;
    border-radius: 3px;
    color: #333;
    cursor: pointer;

    &:hover {
        background: #f0f0f0;
    }

    &:focus-visible {
        outline: 2px solid #2c6cb0;
        outline-offset: 1px;
    }
}

// WCAG 2.4.7: uzytkownik klawiatury musi widziec, ze graf przejal focus —
// inaczej nie wie, ze strzalki zaczely dzialac.
#cytoscape-container:focus-visible {
    outline: 3px solid #2c6cb0;
    outline-offset: -3px;
}
```

- [ ] **Step 6: Zaimportuj partial**

W `src/bpp/static/scss/common.scss`, obok pozostałych importów (linie 7-18),
dopisz:

```scss
@import "graf_powiazan";
```

- [ ] **Step 7: Podepnij przyciski w `controls.js`**

W
`src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js`
dopisz import na górze, obok istniejących:

```javascript
import { przesun, zoomuj, dopasuj } from "./nawigacja.js";
```

Na końcu funkcji `podepnijZdarzenia(ctx)`, przed zamykającym `}`, dopisz:

```javascript
    // --- nawigacja bez przeciagania (WCAG 2.5.7) ---
    const KIERUNKI = {
        "graf-nav-gora": "gora",
        "graf-nav-dol": "dol",
        "graf-nav-lewo": "lewo",
        "graf-nav-prawo": "prawo"
    };
    Object.keys(KIERUNKI).forEach(function (id) {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener("click", function () {
                przesun(cy, KIERUNKI[id]);
            });
        }
    });

    const btnZoomIn = document.getElementById("graf-nav-zoom-in");
    if (btnZoomIn) {
        btnZoomIn.addEventListener("click", function () {
            zoomuj(cy, 1.2);
        });
    }

    const btnZoomOut = document.getElementById("graf-nav-zoom-out");
    if (btnZoomOut) {
        btnZoomOut.addEventListener("click", function () {
            zoomuj(cy, 1 / 1.2);
        });
    }

    const btnDopasuj = document.getElementById("graf-nav-dopasuj");
    if (btnDopasuj) {
        btnDopasuj.addEventListener("click", function () {
            dopasuj(cy);
        });
    }
```

- [ ] **Step 8: Przebuduj front i uruchom testy**

```bash
grunt build
uv run pytest src/powiazania_autorow/tests/test_graf_dostepnosc.py -v
npx vitest run tests/js/nawigacja-grafu.test.js
```

Oczekiwane: 4 passed (pytest), 12 passed (vitest).

- [ ] **Step 9: Commit**

```bash
git add src/powiazania_autorow/templates/powiazania_autorow/graf.html \
    src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js \
    src/bpp/static/scss/graf_powiazan.scss \
    src/bpp/static/scss/common.scss \
    src/powiazania_autorow/tests/
git commit -m "feat(wcag): przyciski nawigacji po grafie bez przeciagania (2.5.7)"
```

---

### Task 5: Obsługa grafu klawiaturą

**Files:**
- Modify: `src/powiazania_autorow/templates/powiazania_autorow/graf.html:158-166` (atrybuty kontenera)
- Modify: `src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js` (handler `keydown`)
- Test: `src/powiazania_autorow/tests/test_graf_dostepnosc.py` (dopisanie)

**Interfaces:**
- Consumes: `przesun`, `zoomuj`, `dopasuj` z Task 3
- Produces: nic dla dalszych zadań

- [ ] **Step 1: Dopisz testy**

Do `src/powiazania_autorow/tests/test_graf_dostepnosc.py` dopisz:

```python
def test_kontener_grafu_jest_fokusowalny():
    # Bez tabindex użytkownik klawiatury nigdy nie dotrze do grafu.
    tresc = _tresc()
    fragment = tresc.split('id="cytoscape-container"')[1][:600]

    assert 'tabindex="0"' in fragment


def test_kontener_grafu_ma_role_application():
    # Bez tego czytnik ekranu w trybie przeglądania sam obsłuży strzałki
    # i nigdy nie dotrą one do grafu.
    tresc = _tresc()
    fragment = tresc.split('id="cytoscape-container"')[1][:600]

    assert 'role="application"' in fragment


def test_kontener_grafu_opisuje_dostepne_klawisze():
    # role="application" wycisza tryb przeglądania, więc aria-label jest
    # jedynym sposobem, w jaki użytkownik pozna dostępne klawisze.
    tresc = _tresc()
    fragment = tresc.split('id="cytoscape-container"')[1][:600]

    assert "aria-label=" in fragment
    for slowo in ("trzałk", "Home"):
        assert slowo in fragment
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
uv run pytest src/powiazania_autorow/tests/test_graf_dostepnosc.py -v
```

Oczekiwane: trzy nowe FAIL.

- [ ] **Step 3: Dodaj atrybuty kontenera**

W `src/powiazania_autorow/templates/powiazania_autorow/graf.html`, element
`#cytoscape-container` (linie 158-166), dopisz trzy atrybuty przed
`style=`:

```django
             tabindex="0"
             role="application"
             aria-label="Graf powiązań autorów. Strzałki przesuwają widok, plus i minus przybliżają, klawisz Home dopasowuje graf do ekranu."
```

- [ ] **Step 4: Dodaj handler klawiatury w `controls.js`**

Na końcu funkcji `podepnijZdarzenia(ctx)`, po kodzie przycisków z Task 4,
dopisz:

```javascript
    // --- obsluga klawiatura (WCAG 2.1.1) ---
    // Klawisze `+`/`-` sa znakami drukowalnymi, wiec podlegaja tez 2.1.4 —
    // spelniaja je trzecim wariantem kryterium: dzialaja WYLACZNIE gdy
    // kontener grafu ma focus, bo handler wisi na nim, nie na `document`.
    const kontener = document.getElementById("cytoscape-container");
    if (kontener) {
        kontener.addEventListener("keydown", function (e) {
            let obsluzone = true;

            switch (e.key) {
                case "ArrowUp": przesun(cy, "gora"); break;
                case "ArrowDown": przesun(cy, "dol"); break;
                case "ArrowLeft": przesun(cy, "lewo"); break;
                case "ArrowRight": przesun(cy, "prawo"); break;
                case "+":
                case "=": zoomuj(cy, 1.2); break;
                case "-":
                case "_": zoomuj(cy, 1 / 1.2); break;
                case "Home": dopasuj(cy); break;
                default: obsluzone = false;
            }

            // preventDefault WYLACZNIE dla obsluzonych klawiszy. Blokowanie
            // wszystkiego zamknelo by Tab w grafie, czyli naprawiajac 2.1.1
            // stworzylibysmy pulapke klawiaturowa i zlamali 2.1.2.
            if (obsluzone) {
                e.preventDefault();
            }
        });
    }
```

Warianty `=` i `_` są obok `+` i `-`, bo na większości układów klawiatury
`+` wymaga Shift.

- [ ] **Step 5: Przebuduj front i uruchom testy**

```bash
grunt build
uv run pytest src/powiazania_autorow/tests/test_graf_dostepnosc.py -v
```

Oczekiwane: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/powiazania_autorow/templates/powiazania_autorow/graf.html \
    src/powiazania_autorow/static/powiazania_autorow/js/powiazania/controls.js \
    src/powiazania_autorow/tests/test_graf_dostepnosc.py
git commit -m "feat(wcag): obsluga grafu powiazan klawiatura (2.1.1, 2.4.7)"
```

---

### Task 6: Testy Playwright

Testy szablonowe i jednostkowe nie dowodzą, że mechanizm **działa**. Bez
tego zadania usunięcie warunku z handlera nie wywaliłoby niczego.

**Files:**
- Create: `src/integration_tests/test_wcag_skrot_i_graf.py`

**Interfaces:**
- Consumes: `#bpp-przelacznik-skrotow` (Task 2), `#graf-nav-*` (Task 4),
  `tabindex` na `#cytoscape-container` (Task 5)
- Produces: nic

- [ ] **Step 1: Poznaj wzorzec z tego projektu**

Sygnatura testu przeglądarkowego w BPP (z
`src/integration_tests/test_siec3d_bez_webgl.py:44-57`):

```python
@pytest.mark.django_db(transaction=True)
def test_cos(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    page.goto(f"{channels_live_server.url}{url}", wait_until="domcontentloaded")
```

Trzy fixture: `channels_live_server`, `page: Page`, `transactional_db`.
Autora tworzy się przez `baker.make(Autor, …, pokazuj=True)` — nie ma
gotowej fixture autora dla tych testów. URL składa się przez f-string, bez
`+`. Import: `from playwright.sync_api import Page, expect`.

**Wymaganie wstępne:** `make assets` — bez zbudowanego bundla strona nie ma
czego wykonać i testy padną.

- [ ] **Step 2: Napisz testy**

Utwórz `src/integration_tests/test_wcag_skrot_i_graf.py`:

```python
"""WCAG 2.1.4 i 2.5.7/2.1.1 — testy zachowania w przeglądarce.

Testy szablonowe dowodzą, że kod jest w pliku; te dowodzą, że działa.
Bez nich usunięcie warunku `bppSkrotyWlaczone()` z handlera albo
`preventDefault` z obsługi klawiatury nie wywaliłoby żadnego testu.
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Autor


def _url_autora(channels_live_server):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    return (
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor', args=[autor.slug])}"
    )


@pytest.mark.django_db(transaction=True)
def test_skrot_otwiera_wyszukiwarke_domyslnie(
    channels_live_server, page: Page, transactional_db
):
    page.goto(_url_autora(channels_live_server), wait_until="domcontentloaded")

    page.keyboard.press("/")

    expect(page.locator("#globalSearchModal")).to_be_visible(timeout=5000)


@pytest.mark.django_db(transaction=True)
def test_wylaczenie_skrotu_dziala(
    channels_live_server, page: Page, transactional_db
):
    page.goto(_url_autora(channels_live_server), wait_until="domcontentloaded")

    page.locator("#bpp-przelacznik-skrotow").click()
    page.keyboard.press("/")
    page.wait_for_timeout(500)

    expect(page.locator("#globalSearchModal")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_ponowne_wlaczenie_przywraca_skrot(
    channels_live_server, page: Page, transactional_db
):
    page.goto(_url_autora(channels_live_server), wait_until="domcontentloaded")

    przelacznik = page.locator("#bpp-przelacznik-skrotow")
    przelacznik.click()
    przelacznik.click()
    page.keyboard.press("/")

    expect(page.locator("#globalSearchModal")).to_be_visible(timeout=5000)


@pytest.mark.django_db(transaction=True)
def test_przelacznik_aktualizuje_aria_pressed(
    channels_live_server, page: Page, transactional_db
):
    page.goto(_url_autora(channels_live_server), wait_until="domcontentloaded")

    przelacznik = page.locator("#bpp-przelacznik-skrotow")
    expect(przelacznik).to_have_attribute("aria-pressed", "true")

    przelacznik.click()
    expect(przelacznik).to_have_attribute("aria-pressed", "false")


@pytest.mark.django_db(transaction=True)
def test_preferencja_przezywa_przeladowanie(
    channels_live_server, page: Page, transactional_db
):
    url = _url_autora(channels_live_server)
    page.goto(url, wait_until="domcontentloaded")

    page.locator("#bpp-przelacznik-skrotow").click()
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#bpp-przelacznik-skrotow")).to_have_attribute(
        "aria-pressed", "false"
    )
```

Widok strony autora został wybrany zamiast strony uczelni, bo nie wymaga
obiektu `Uczelnia` w bazie, a stopka i modal wyszukiwarki renderują się na
nim tak samo. `bpp:browse_autor` ma dwa warianty URL-a — po `pk`
(`urls.py:274`) i po `slug` (`urls.py:300`); `reverse` z argumentem `slug`
trafia w drugi. `Autor` tworzony przez `baker.make` dostaje slug
automatycznie (pole wyliczane przy zapisie).

**Nie zamieniaj** testu zachowania na sprawdzenie obecności elementu w
HTML-u — testy szablonowe z Task 2 już to pokrywają, ten plik ma dowodzić
działania.

- [ ] **Step 3: Uruchom testy**

```bash
make assets
make playwright-install
uv run pytest src/integration_tests/test_wcag_skrot_i_graf.py -v
```

Pierwszy przebieg bywa wolny (zimny start testcontenerów) i `page.goto`
potrafi raz timeoutnąć — wtedy ponów.

Jeżeli nazwa fixture live-servera albo widoku (`bpp:browse_uczelnia`) nie
pasuje, dostosuj ją do wzorca z kroku 1 — ale **nie** zamieniaj testu
zachowania na test obecności elementu w HTML-u. Testy szablonowe już to
pokrywają; ten plik ma dowodzić działania.

Jeżeli strona uczelni nie renderuje przełącznika (np. wymaga obiektu
`Uczelnia` w bazie), utwórz go w teście przez `baker.make` albo użyj
istniejącej fixture — sprawdź `src/fixtures/conftest_*.py`.

- [ ] **Step 4: Dopisz test grafu**

Do tego samego pliku dopisz:

```python
def _url_grafu(channels_live_server):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    return (
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor_powiazania', args=[autor.pk])}"
    )


@pytest.mark.django_db(transaction=True)
def test_graf_ma_przyciski_nawigacji_i_jest_fokusowalny(
    channels_live_server, page: Page, transactional_db
):
    page.goto(_url_grafu(channels_live_server), wait_until="domcontentloaded")

    kontener = page.locator("#cytoscape-container")
    expect(kontener).to_have_attribute("tabindex", "0")
    expect(page.locator("#graf-nav-dopasuj")).to_be_visible(timeout=10000)

    page.locator("#graf-nav-dopasuj").click()


@pytest.mark.django_db(transaction=True)
def test_graf_nie_jest_pulapka_klawiaturowa(
    channels_live_server, page: Page, transactional_db
):
    # Handler robi preventDefault WYŁĄCZNIE dla obsłużonych klawiszy. Gdyby
    # blokował wszystko, Tab przestałby wyprowadzać focus — czyli naprawiając
    # 2.1.1 stworzylibyśmy pułapkę klawiaturową i złamali 2.1.2.
    page.goto(_url_grafu(channels_live_server), wait_until="domcontentloaded")

    page.locator("#cytoscape-container").focus()
    page.keyboard.press("Tab")

    assert page.evaluate("document.activeElement.id") != "cytoscape-container"
```

Widok `bpp:browse_autor_powiazania` przyjmuje `pk` — potwierdzone w
`test_siec3d_bez_webgl.py:67`, gdzie ten sam URL jest budowany przez
`reverse("bpp:browse_autor_powiazania", args=[autor.pk])`.

Jeżeli graf nie renderuje się dla autora bez powiązań i przyciski nie
pojawią się w DOM, sprawdź warunek widoczności sieci
(`Autor.czy_pokazywac_siec_powiazan`) i ustaw wymagane pole przez
`baker.make`. Nakładka jest w szablonie statycznie, więc powinna być obecna
niezależnie od danych — jeśli tak nie jest, zgłoś to jako znalezisko, bo
oznaczałoby, że nawigacja znika akurat przy pustym grafie.

- [ ] **Step 5: Uruchom całość i commit**

```bash
uv run pytest src/integration_tests/test_wcag_skrot_i_graf.py -v
git add src/integration_tests/test_wcag_skrot_i_graf.py
git commit -m "test(wcag): testy przegladarkowe skrotu i nawigacji po grafie"
```

---

### Task 7: Wykaz odroczonych i newsfragment

**Files:**
- Modify: `docs/superpowers/specs/2026-08-06-wcag-naprawy-stwierdzone-design.md`
- Modify: `docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md`
- Create: `src/bpp/newsfragments/wcag-skrot-i-graf.feature.rst`

**Interfaces:**
- Consumes: nic
- Produces: nic

- [ ] **Step 1: Usuń 2.1.4 i 2.5.7 z wykazu w dokumencie 08-06**

W sekcji „Wykaz odroczonych niezgodności" zastąp wpisy o 2.1.4 i 2.5.7
jednym akapitem:

```markdown
**2.1.4 i 2.5.7 — domknięte 2026-08-07.**
Oba kryteria zostały naprawione w kolejnej iteracji: skrót `/` dostał
mechanizm wyłączania (localStorage + przełącznik w stopce), graf powiązań —
przyciski nawigacji i obsługę klawiaturą. Szczegóły:
`2026-08-07-wcag-skrot-i-graf-design.md`.
```

- [ ] **Step 2: To samo w dokumencie 08-05**

Ten sam akapit w sekcji „Odroczone niezgodności".

- [ ] **Step 3: Przejrzyj oba dokumenty pod kątem pozostałych wzmianek**

Poprzednia iteracja pokazała, że dokument o rozbudowanej historii zostawia
twierdzenia sprzeczne ze stanem faktycznym w miejscach, o których się nie
myśli — trzy kolejne przejścia znajdowały kolejne.

```bash
grep -n "2\.1\.4\|2\.5\.7\|skrót\|skrot\|graf\|przeciąganie" \
    docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md \
    docs/superpowers/specs/2026-08-06-wcag-naprawy-stwierdzone-design.md
```

Dla KAŻDEGO trafienia rozstrzygnij, czy twierdzenie jest nadal prawdziwe.
Miejsca mówiące „odroczone", „niezgodne", „świadomie nie naprawiamy" dla
tych dwóch kryteriów wymagają dopisku
`**Korekta (2026-08-07):**` — zgodnie z konwencją przyjętą w tych
dokumentach, bez usuwania oryginalnego tekstu.

W raporcie wymień **wszystkie** sprawdzone miejsca, także uznane za
niewymagające zmiany, z uzasadnieniem.

- [ ] **Step 4: Napisz newsfragment**

Utwórz `src/bpp/newsfragments/wcag-skrot-i-graf.feature.rst`:

```rst
Skrót klawiszowy ``/`` otwierający wyszukiwarkę można teraz wyłączyć —
przełącznik „Skróty klawiszowe" znajduje się w stopce strony. Ma to
znaczenie dla osób korzystających ze sterowania głosem, którym pojedyncze
znaki mimowolnie uruchamiały wyszukiwarkę (kryterium WCAG 2.2 AA 2.1.4).
Przy okazji naprawiono zdublowany obsługiwacz tego skrótu.

Graf powiązań autorów da się teraz przesuwać i przybliżać przyciskami oraz
klawiaturą (strzałki, plus, minus, Home), a nie wyłącznie przeciąganiem
myszą — kryteria 2.5.7 i 2.1.1.
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/ src/bpp/newsfragments/wcag-skrot-i-graf.feature.rst
git commit -m "docs(wcag): domkniecie 2.1.4 i 2.5.7 w wykazie, newsfragment"
```

---

### Task 8: Weryfikacja końcowa

- [ ] **Step 1: Pełna suita Pythona**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-faza2
make tests-without-playwright
```

Trwa do ~10 minut. Poczekaj w swojej turze, nie uruchamiaj w tle.

- [ ] **Step 2: Testy JS**

```bash
make js-tests
```

- [ ] **Step 3: Testy Playwright**

```bash
make assets
make tests-only-playwright
```

- [ ] **Step 4: pre-commit**

```bash
pre-commit
```

BEZ ARGUMENTÓW. Problemy naprawiaj ręcznie, edytorem, po jednym.

- [ ] **Step 5: Spójność gałęzi**

```bash
git log --oneline fix-wcag-naprawy-stwierdzone..HEAD
git diff --stat fix-wcag-naprawy-stwierdzone..HEAD
uv run python src/manage.py makemigrations --check --dry-run
```

Gałąź jest **stacked** na `fix-wcag-naprawy-stwierdzone`, więc bazą
porównania jest ta gałąź, nie `dev`.

Dryf migracji w pakietach zewnętrznych (favicon, flexible_reports, siteblog)
jest zastany — zweryfikowano to w poprzedniej iteracji. Dryf w pakietach
`bpp`/`powiazania_autorow` byłby znaleziskiem: zgłoś, nie twórz migracji.

- [ ] **Step 6: Obejrzyj efekt w przeglądarce**

```bash
uv run run-site run --from-dump ~/db-backup-20260428-093811.pg_dump --no-browser
```

Sprawdź: przełącznik w stopce zmienia etykietę i faktycznie wyłącza skrót;
na stronie autora z włączoną siecią powiązań przyciski przesuwają graf, a
Tab dochodzi do kontenera i strzałki działają.
