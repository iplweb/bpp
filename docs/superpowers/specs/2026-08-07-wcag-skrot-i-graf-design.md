# Skrót `/` i nawigacja po grafie powiązań — WCAG 2.1.4, 2.5.7, 2.1.1

Data: 2026-08-07
Poprzednik: `2026-08-06-wcag-naprawy-stwierdzone-design.md`
Gałąź: `fix-wcag-2140-2570`, stacked na `fix-wcag-naprawy-stwierdzone` (PR #732)

## Cel

Domknąć dwa kryteria WCAG 2.2 AA, które poprzednia iteracja **świadomie
odroczyła**, wpisując je do wykazu niezgodności:

- **2.1.4 Character Key Shortcuts (A)** — skrót `/` wiązany na `document`
- **2.5.7 Dragging Movements (AA)** — nawigacja po grafie powiązań wyłącznie
  przez przeciąganie

Przy okazji grafu domykamy też **2.1.1 Keyboard (A)** — obsługa klawiaturą
kosztuje niewiele, gdy funkcje nawigacyjne i tak powstają dla przycisków.

Odroczenie z 2026-08-06 miało uzasadnienie: brak nacisku regulacyjnego i brak
odbiorcy raportu. Ta iteracja jest decyzją, żeby mimo to poprawić dostępność
tam, gdzie koszt jest znany i ograniczony.

## Zakres

**Wchodzi:**

- 2.1.4 — mechanizm wyłączania skrótów jednoznakowych (localStorage)
- 2.5.7 — przyciski nawigacji po grafie (kierunki, zoom, dopasowanie)
- 2.1.1 — obsługa grafu klawiaturą (strzałki, `+`/`−`, `Home`)
- 2.4.7 — widoczny pierścień focusa na kontenerze grafu
- usunięcie obu kryteriów z wykazu odroczonych w obu specyfikacjach

**Nie wchodzi:**

- 3.1.2 dla tytułu przełożonego (wymaga nowego pola w modelu)
- bramka CI z axe-core, skan szeroki, audyt ręczny, raport zgodności
- 2.5.8 (rozmiar celów dotykowych) w skali całego serwisu — ale **nowe**
  przyciski muszą spełniać to kryterium, patrz „Część B"

## Część A — 2.1.4, skrót `/`

### Problem

`src/django_bpp/templates/base.html:39-49` wiąże handler na `document`:

```javascript
document.addEventListener('keydown', function(e) {
    if (e.key === '/' && !$(e.target).is('input, textarea, select')) {
        e.preventDefault();
        if (typeof openGlobalSearch === 'function') {
            openGlobalSearch(null, true);
        }
    }
});
```

Wykluczenie pól formularza nie wystarcza: gdy focus spoczywa na `body`,
linku albo przycisku, naciśnięcie `/` porywa klawisz. Kryterium wymaga
spełnienia **jednego z trzech** warunków — wyłączalności, przemapowania albo
aktywności wyłącznie przy focusie komponentu. Handler nie spełnia żadnego.

Kryterium chroni przede wszystkim użytkowników sterowania głosem, których
wejściem są ciągi liter, oraz osoby z drżeniem rąk.

### Wybrane wyjście: mechanizm wyłączania

Wzorce branżowe potwierdzają ten kierunek. GitHub trzyma to jako ustawienie
konta („You can disable character key shortcuts, while still allowing
shortcuts that use modifier keys, in your accessibility settings"), Gmail
udostępnia dialog pod `?` z przełącznikiem.

Obie realizacje zakładają jednak **zalogowanego użytkownika z profilem**, a
audytowany zakres BPP to część publiczna, anonimowa. Funkcjonalnym
odpowiednikiem jest `localStorage`: nie wymaga konta, przeżywa sesję, działa
per przeglądarka. Kryterium nie wymaga trwałości między urządzeniami — tylko
istnienia mechanizmu.

Odrzucone alternatywy:

- **zawężenie do focusa w polu wyszukiwania** — zgodne, ale skrót traci sens:
  mając focus w wyszukiwarce wystarczy pisać;
- **modyfikator (`Alt+/`)** — wyprowadza skrót spoza kryterium jednym
  ruchem, ale łamie konwencję branżową (`/` w GitHub, Gmail, Slack), a
  `Alt+/` bywa zajęty przez czytniki ekranu;
- **całkowite usunięcie** — pełna zgodność zerowym kosztem, ale odbiera
  działającą wygodę użytkownikom klawiatury;
- **przełącznik w obiekcie `Uczelnia`** — wyłączenie przez administratora
  **nie spełnia** kryterium: WCAG wymaga mechanizmu dostępnego dla
  użytkownika.

### Komponenty

**Moduł preferencji** — `src/bpp/static/bpp/js/skroty-klawiszowe.js`.
Jedna odpowiedzialność: odczyt i zapis preferencji.

- klucz `localStorage`: `bpp.skrotyJednoznakowe`, wartości `"1"` / `"0"`
- `window.bppSkrotyWlaczone()` → `boolean`, **domyślnie `true`** (brak wpisu
  = zachowanie niezmienione dla każdego, kto nic nie ustawił)
- `window.bppUstawSkroty(bool)` → zapisuje i zwraca nowy stan
- odporny na niedostępny `localStorage` (tryb prywatny, wyczerpany limit,
  wyłączone ciasteczka): `try`/`catch` wokół obu operacji, w razie błędu
  zwraca wartość domyślną zamiast rzucać wyjątkiem

**Handler** w `base.html` — jeden dodatkowy warunek przed reakcją:

```javascript
if (e.key === '/' && window.bppSkrotyWlaczone()
    && !$(e.target).is('input, textarea, select')) {
```

Moduł ładowany przed inline'owym blokiem, tym samym wzorcem co
`related-records-highlight.js` w poprzedniej iteracji.

**Przełącznik w stopce** — `src/django_bpp/templates/base_footer.html`.

Przycisk (`<button type="button">`) z etykietą „Skróty klawiszowe: włączone"
/ „…: wyłączone", przełączający stan i tekst bez przeładowania strony.
Atrybut `aria-pressed` odzwierciedla stan, żeby czytnik ogłaszał zmianę.

**Dlaczego stopka, a nie strona deklaracji dostępności** — mimo że to
naturalniejsze miejsce na ustawienia dostępności: deklaracja jest w BPP
konfigurowalna per uczelnia (`Uczelnia.pokazuj_deklaracje_dostepnosci`:
wartość 1 → zewnętrzny URL uczelni, 2 → wewnętrzna strona BPP, brak → brak
linku). Na części wdrożeń strony nie ma wcale, na innych prowadzi na serwer
uczelni, gdzie nie postawimy przełącznika. Mechanizm ukryty za opcjonalną
stroną nie spełnia wymogu „dostępny". Stopka (`base_footer.html`,
renderowana z `base.html`) jest zawsze.

## Część B — 2.5.7, nawigacja po grafie wskaźnikiem

### Problem

`src/powiazania_autorow/templates/powiazania_autorow/graf.html` to widok
publiczny, bramkowany per uczelnia (`czy_pokazywac_siec_powiazan`,
`src/bpp/views/browse.py:245`). Wizualizacja stoi na Cytoscape.js; jedyną
drogą przesunięcia widoku jest przeciąganie.

Kryterium wymaga alternatywy realizowanej **pojedynczym wskaźnikiem** —
kliknięciem lub tapnięciem. Obsługa klawiaturą (część C) jest odrębnym
kryterium i nie zastępuje tego wymogu.

Wyszukiwarka węzłów (`powiazania/search.js`) istnieje, ale jedynie
podświetla trafienia i przygasza resztę — **nie przesuwa widoku**, więc
zobaczenie trafienia nadal wymaga przeciągnięcia grafu. Nie jest zatem
alternatywą w rozumieniu kryterium.

### Komponenty

**Moduł nawigacji** —
`src/powiazania_autorow/static/powiazania_autorow/js/powiazania/nawigacja.js`.
Czyste funkcje nad instancją Cytoscape, testowalne z atrapą:

- `przesun(cy, kierunek)` — `kierunek` ∈ `"gora" | "dol" | "lewo" | "prawo"`
- `zoomuj(cy, wspolczynnik)` — `wspolczynnik` > 1 przybliża, < 1 oddala;
  zoom wokół środka widoku (`cy.zoom({level, renderedPosition})`)
- `dopasuj(cy)` — `cy.fit()` z niewielkim marginesem

**Krok przesunięcia liczony jako procent rozmiaru widoku** (20% szerokości
lub wysokości), nie stała w pikselach. Przy dużym przybliżeniu stały krok
byłby ledwo zauważalny, przy oddaleniu — przeskakiwałby cały graf.

**Współczynnik zoomu**: 1,2 na krok, z ograniczeniem do zakresu ustawionego
w instancji Cytoscape (`cy.minZoom()` / `cy.maxZoom()`), żeby przyciski nie
wyprowadzały widoku poza dopuszczalne wartości.

**Nakładka z przyciskami** — w `graf.html`, wewnątrz istniejącego
`#graf-wrapper` (ma już `position: relative`, więc nakładka nie zmienia
układu strony). Siedem przycisków: cztery kierunki, `+`, `−`, „dopasuj do
ekranu".

**Podpięcie zdarzeń** w istniejącym `powiazania/controls.js`, zgodnie z
tamtejszym wzorcem (`podepnijZdarzenia(ctx)`).

**Style** — nowy partial `src/bpp/static/scss/_graf_powiazan.scss`,
zaimportowany w `common.scss` obok pozostałych (`@import "graf_powiazan";`).

Aplikacja `powiazania_autorow` **nie ma własnego katalogu SCSS** — `graf.html`
stosuje style inline w atrybutach `style=""` (np. `#graf-legenda`:
`position: absolute; top: 10px; right: 10px`). Nakładkę nawigacji mimo to
opisujemy w SCSS, nie inline, z dwóch powodów: pierścień focusa wymaga
pseudoklasy `:focus-visible` (część C), której w atrybucie `style` zapisać
się nie da, a rozbijanie jednego komponentu między atrybut i arkusz byłoby
gorsze niż trzymanie go w całości w arkuszu.

Pozycjonowanie absolutne wewnątrz `#graf-wrapper`, w rogu **przeciwległym do
legendy** — legenda zajmuje prawy górny (`top: 10px; right: 10px`), więc
nawigacja idzie w lewy dolny.

Po zmianie SCSS wymagany `grunt build` (albo `make assets`).

### Dostępność samych przycisków

- `type="button"` — bez tego przycisk wewnątrz formularza wysyła go
- `aria-label` po polsku („Przesuń widok w lewo", „Przybliż", „Dopasuj graf
  do ekranu") — sam glif strzałki nic nie mówi czytnikowi
- **rozmiar celu ≥ 24×24 px CSS** — kryterium 2.5.8 (AA). Naprawiając 2.5.7
  nie wolno złamać sąsiedniego kryterium; to jedyne miejsce w tej iteracji,
  gdzie 2.5.8 obowiązuje nas wprost, bo tworzymy nowe cele dotykowe
- glify jako tekst (`↑`, `+`, `⤢`) z `aria-hidden="true"`, treść dla
  czytnika wyłącznie w `aria-label`

## Część C — 2.1.1, obsługa grafu klawiaturą

### Komponenty

**Kontener** `#cytoscape-container` w `graf.html`:

- `tabindex="0"` — wchodzi w kolejność tabulacji
- `role="application"` — sygnalizuje czytnikowi, że komponent przechwytuje
  klawisze strzałek (bez tego czytnik w trybie przeglądania sam je obsłuży)
- `aria-label` wymieniający dostępne klawisze, np. „Graf powiązań autorów.
  Strzałki przesuwają widok, plus i minus przybliżają, Home dopasowuje graf
  do ekranu."

**Handler `keydown`** na kontenerze, wołający te same funkcje co przyciski:

| klawisz | akcja |
|---|---|
| `ArrowUp` / `ArrowDown` / `ArrowLeft` / `ArrowRight` | `przesun` |
| `+` / `=` | `zoomuj` (przybliż) |
| `-` / `_` | `zoomuj` (oddal) |
| `Home` | `dopasuj` |

`preventDefault()` **wyłącznie dla klawiszy obsłużonych** — `Tab`, `Escape`
i reszta muszą działać normalnie, inaczej powstaje pułapka klawiaturowa
(kryterium 2.1.2).

Wariant `=` obok `+` bo na większości układów `+` wymaga Shift; `_` obok `-`
symetrycznie.

**Widoczny focus** — pierścień na `#cytoscape-container:focus-visible`
(kryterium 2.4.7). Bez tego użytkownik klawiatury nie wie, że graf przejął
focus i strzałki zaczęły działać.

### Relacja do kryterium 2.1.4

Klawisze `+`, `-`, `=`, `_` są znakami drukowalnymi, więc formalnie podlegają
temu samemu kryterium co skrót `/`. Spełniają je jednak **trzecim** wariantem
— „skrót jest aktywny wyłącznie wtedy, gdy komponent ma focus" — bo handler
wisi na kontenerze grafu, nie na `document`. Nie wymagają przełącznika i
**nie** są objęte preferencją z części A.

To rozgraniczenie jest zamierzone: skrót globalny, którego nie da się przypiąć
do komponentu, dostaje mechanizm wyłączania; skróty lokalne — ograniczenie do
focusa.

## Testy

Konwencja: pytest (funkcje standalone, `@pytest.mark.django_db` gdzie baza),
vitest dla JS (`tests/js/**/*.test.js`).

**Moduł preferencji skrótów** (vitest, atrapa `localStorage`):
- brak wpisu → `true` (domyślka)
- `"0"` → `false`; `"1"` → `true`
- `bppUstawSkroty(false)` zapisuje `"0"` i zwraca `false`
- rzucający `localStorage` (tryb prywatny) → zwraca domyślkę, nie wyjątek
- `getItem` zwracający śmieci (`"tak"`) → domyślka

**Moduł nawigacji grafu** (vitest, atrapa `cy` z `pan`, `zoom`, `fit`,
`width`, `height`, `minZoom`, `maxZoom`):
- `przesun` w każdym z czterech kierunków zmienia właściwą oś i znak
- krok skaluje się z rozmiarem widoku (dwa różne `width` → dwa różne kroki)
- `zoomuj` nie przekracza `minZoom`/`maxZoom`
- `dopasuj` woła `cy.fit()`

**Szablony** (pytest):
- stopka zawiera przycisk przełącznika z `aria-pressed`
- `graf.html` zawiera siedem przycisków nawigacji, każdy z `aria-label`
- `#cytoscape-container` ma `tabindex="0"`, `role`, `aria-label`
- moduły JS są podpięte (`<script src>` obecny w renderze) — inaczej
  usunięcie tagu nie wywali żadnego testu, a funkcja przestanie działać

**Playwright** — `src/integration_tests/`, obok istniejącego
`test_siec3d_bez_webgl.py` (jedyny dotychczasowy test przeglądarkowy
wizualizacji powiązań; testy widoków grafu bez przeglądarki żyją w
`src/powiazania_autorow/test_views.py`):
- klik w „dopasuj" zmienia zoom/pan grafu
- Tab dochodzi do kontenera grafu, strzałka przesuwa widok
- `Tab` po sfokusowaniu grafu **wychodzi** z niego (brak pułapki, 2.1.2)

Weryfikacja przed PR: `make tests-without-playwright`, `make js-tests`,
`make tests-only-playwright`, `pre-commit` (bez argumentów).

## Aktualizacja wykazu odroczonych

Wpisy o 2.1.4 i 2.5.7 znikają z sekcji „Odroczone niezgodności" w **obu**
specyfikacjach (`2026-08-06-…` i `2026-08-05-…`) i zostają zastąpione notą, że
kryteria domknięto 2026-08-07 wraz z odsyłaczem do tego dokumentu.

Poprzednia iteracja pokazała, że dokument o rozbudowanej historii łatwo
zostawia twierdzenia sprzeczne ze stanem faktycznym — trzy kolejne przejścia
znajdowały kolejne. Dlatego przy tej zmianie trzeba przejrzeć **wszystkie**
wystąpienia `2.1.4`, `2.5.7`, „skrót", „graf", „przeciąganie", „naprawa
stwierdzona" i wymienić w raporcie także miejsca uznane za niewymagające
zmiany, wraz z uzasadnieniem.

Nadal odroczone (bez zmian): 3.1.2 dla tytułu przełożonego, warunki po
stronie wdrożenia (`kod_bcp47`, własny szablon opisu, override allowlisty,
wiersz `opis_bibliograficzny.html` w `dbtemplates`).

## Ryzyka

**`role="application"` wycisza tryb przeglądania czytnika.** Wewnątrz takiego
regionu czytnik przekazuje klawisze do aplikacji zamiast obsługiwać je
własną nawigacją. To zamierzone (inaczej strzałki nie dotrą do grafu), ale
oznacza, że `aria-label` musi wyczerpująco opisać dostępne klawisze — poza
nim użytkownik nie ma jak ich odkryć.

**Nakładka może zasłonić graf na wąskich ekranach.** Przyciski zajmują róg
kontenera; przy małej wysokości widoku mogą przykryć węzły. Mitygacja:
lewy dolny róg (legenda zajmuje prawy górny), półprzezroczyste tło jak w
legendzie.

**Nowy partial SCSS obok stylów inline.** `graf.html` opisuje dziś cały
wygląd atrybutami `style=""`; dokładamy do niego arkusz. Rozbicie jest
świadome (patrz „Style"), ale oznacza, że kolejna osoba zmieniająca wygląd
grafu musi zajrzeć w dwa miejsca. Alternatywa — przeniesienie całego wyglądu
grafu do SCSS — byłaby refaktorem poza zakresem tej iteracji.

**Skrót `/` wyłączony w localStorage nie przenosi się między przeglądarkami.**
Użytkownik sterowania głosem, który wyłączył skróty na jednym urządzeniu,
napotka je ponownie na innym. Kryterium tego nie wymaga, ale warto odnotować
w wykazie jako ograniczenie znane.

**Domyślka „włączone" oznacza, że problem trwa do momentu wyłączenia.**
Alternatywą byłoby domyślne wyłączenie, ale odebrałoby to działającą funkcję
wszystkim dotychczasowym użytkownikom. Kryterium wymaga mechanizmu, nie
domyślnego wyłączenia.

## Poza zakresem

- bramka CI z axe-core, baseline, strona wzorników
- skan szeroki na dumpie, audyt ręczny WCAG-EM, raport zgodności
- 2.5.8 w skali serwisu (obowiązuje nas tylko dla nowych przycisków)
- panel zalogowanego użytkownika i Django admin
- poziom AAA
