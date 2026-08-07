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

- 2.1.4 — mechanizm wyłączania skrótów jednoznakowych (localStorage),
  obejmujący **wszystkie** publiczne handlery `/`, nie jeden
- likwidacja zduplikowanego handlera `/` (dziś `openGlobalSearch` woła się
  dwa razy na jedno naciśnięcie) — znalezisko poboczne, naprawiane przy okazji
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

Wykluczenie pól formularza nie wystarcza: gdy focus spoczywa na `body`,
linku albo przycisku, naciśnięcie `/` porywa klawisz. Kryterium wymaga
spełnienia **jednego z trzech** warunków — wyłączalności, przemapowania albo
aktywności wyłącznie przy focusie komponentu. Żaden z istniejących handlerów
nie spełnia żadnego.

Kryterium chroni przede wszystkim użytkowników sterowania głosem, których
wejściem są ciągi liter, oraz osoby z drżeniem rąk.

### Inwentaryzacja: skrót `/` obsługiwany jest w czterech miejscach

To ustalenie jest warunkiem skuteczności całej części A. Objęcie preferencją
jednego handlera nie da nic, dopóki pozostałe reagują niezależnie.

| miejsce | co robi | w zakresie? |
|---|---|---|
| `src/django_bpp/templates/base.html:42` | otwiera wyszukiwarkę globalną | **tak** |
| `src/django_bpp/templates/global_search_modal.html:1048` | otwiera wyszukiwarkę globalną (**duplikat**) | **tak** |
| `src/bpp/templates/browse/uczelnia.html:134` | zamyka baner podpowiedzi | **tak** |
| `src/django_bpp/templates/admin/base_site.html:127` | wyszukiwarka w adminie | nie — panel zalogowanego jest poza zakresem audytu |

Modal jest włączany z `top_bar.html:511`, a ten z `base.html`, więc oba
pierwsze handlery wiszą na `document` **na tej samej stronie**.

**Znalezisko poboczne: dziś oba wołają `openGlobalSearch` na jedno
naciśnięcie.** Handler w `base.html` nie sprawdza stanu modala, handler w
modalu sprawdza (`!$('#globalSearchModal').hasClass('show')`), ale przy
zamkniętym modalu oba warunki są prawdziwe. To istniejący błąd, niezależny
od WCAG.

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
Odpowiedzialność: preferencja użytkownika i jej przełącznik.

- klucz `localStorage`: `bpp.skrotyJednoznakowe`, wartości `"1"` / `"0"`
- `window.bppSkrotyWlaczone()` → `boolean`, **domyślnie `true`** (brak wpisu
  = zachowanie niezmienione dla każdego, kto nic nie ustawił); wartość inna
  niż `"0"`/`"1"` traktowana jak brak wpisu
- `window.bppUstawSkroty(bool)` → zapisuje i zwraca nowy stan
- `window.bppPodepnijPrzelacznikSkrotow(el)` → wiąże `click` na przekazanym
  elemencie, aktualizuje jego tekst i `aria-pressed`
- odporny na niedostępny `localStorage` (tryb prywatny, wyczerpany limit,
  wyłączone ciasteczka): `try`/`catch` wokół obu operacji, w razie błędu
  zwraca wartość domyślną zamiast rzucać wyjątkiem

Trzecia funkcja jest w module celowo: gdyby logika przełącznika została
inline w stopce, nie dałoby się jej przetestować jednostkowo, a moduł
znałby tylko połowę własnego kontraktu.

**Handlery** — warunek dodany w **obu** publicznych miejscach otwierających
wyszukiwarkę oraz w handlerze banera:

```javascript
if (e.key === '/'
    && (typeof window.bppSkrotyWlaczone !== 'function'
        || window.bppSkrotyWlaczone())
    && !$(e.target).is('input, textarea, select')) {
```

Guard `typeof` jest konieczny: gdyby moduł się nie załadował (404, błąd
wcześniejszego skryptu), gołe wywołanie rzucałoby `TypeError` przy każdym
naciśnięciu `/` i skrót umarłby po cichu. Wzorzec jest zgodny z istniejącym
`typeof openGlobalSearch === 'function'` w tym samym handlerze
(`base.html:44`). Przy braku modułu degradujemy do zachowania dotychczasowego.

**Likwidacja duplikatu.** Handler w `base.html:39-49` i ten w
`global_search_modal.html:1040-1052` robią to samo. Zostaje **jeden** — ten
w `global_search_modal.html`, bo sprawdza już stan modala i mieszka obok
kodu, który obsługuje. Handler z `base.html` znika w całości.

To upraszcza część A: zamiast trzech miejsc do objęcia warunkiem zostają
dwa (modal + baner na stronie uczelni).

**Kolejność ładowania nie jest krytyczna.** Handlery rejestrują się wewnątrz
`DOMContentLoaded`, ale preferencję sprawdzają dopiero w momencie
naciśnięcia klawisza — więc moduł musi być obecny przy pierwszym użyciu
skrótu, nie przy rejestracji. Mimo to ładujemy go w `base.html` przed
blokiem skryptów, dla przewidywalności.

**Baner podpowiedzi.** `src/django_bpp/templates/search_banner.html:9`
reklamuje skrót („Wciśnij klawisz `/` (ukośnik) aby szybko znaleźć…").
Przy wyłączonych skrótach baner **nie może się pokazywać** — instrukcja
używania niedziałającej funkcji jest gorsza niż brak instrukcji. Moduł
ukrywa baner, gdy preferencja jest wyłączona.

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
stroną nie spełnia wymogu „dostępny".

**Zasięg stopki.** `base_footer.html` jest włączana z `base.html`, więc stoi
na wszystkich stronach dziedziczących po nim. Strony rozszerzające
bezpośrednio `bare.html` (kreator instalacji, `multiseek/live-results.html`,
podgląd opisu w adminie) stopki nie mają — ale nie mają też handlera `/`,
bo ten żyje w bloku `body` w `base.html`. Mechanizm i skrót pokrywają się
zakresem, więc nie powstaje strona ze skrótem bez możliwości wyłączenia go.

## Część B — 2.5.7, nawigacja po grafie wskaźnikiem

### Problem

`src/powiazania_autorow/templates/powiazania_autorow/graf.html` to widok
publiczny, bramkowany metodą `Autor.czy_pokazywac_siec_powiazan(uczelnia)`
(`src/bpp/views/browse.py:245`) — ustawienie per-autor nadpisuje
per-uczelnia. Wizualizacja stoi na Cytoscape.js (`^3.34.0`); jedyną drogą
przesunięcia widoku jest przeciąganie.

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
przy tworzeniu instancji — `utworzCy` (`powiazania/cy.js:99-100`) ustawia
`minZoom: 0.1`, `maxZoom: 4`. Moduł odczytuje je przez `cy.minZoom()` /
`cy.maxZoom()`, nie zaszywa liczb u siebie.

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

Pozycjonowanie absolutne wewnątrz `#graf-wrapper`. Trzy z czterech rogów są
już zajęte:

| róg | zajmuje | kiedy widoczny |
|---|---|---|
| lewy górny | `#graf-panel` (`graf.html:183`) | po kliknięciu węzła |
| prawy górny | `#graf-legenda` (`graf.html:167`) | zawsze |
| lewy dolny | `#graf-notka` (`graf.html:191`) | gdy sieć przycięta (`data.truncated`) |
| **prawy dolny** | — | — |

Nakładka idzie w **prawy dolny**. Lewy dolny odpada mimo pozornej wolności:
`#graf-notka` pojawia się dokładnie przy dużych sieciach, czyli wtedy, gdy
nawigacja jest najbardziej potrzebna.

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

**Moduł preferencji skrótów** (vitest). Moduł jest skryptem window-globalnym
(jak `djangoql-*.js`), więc plik testowy deklaruje u siebie
`// @vitest-environment jsdom` — domyślnym środowiskiem w `vitest.config.js`
jest `node`, w którym nie ma `window` ani `localStorage`.

- brak wpisu → `true` (domyślka)
- `"0"` → `false`; `"1"` → `true`
- `getItem` zwracający śmieci (`"tak"`) → domyślka
- `bppUstawSkroty(false)` zapisuje `"0"` i zwraca `false`
- rzucający `localStorage` (tryb prywatny) → zwraca domyślkę, nie wyjątek
- `bppPodepnijPrzelacznikSkrotow(el)` — klik odwraca stan, aktualizuje
  `aria-pressed` i tekst; drugi klik wraca do stanu wyjściowego

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
- `skroty-klawiszowe.js` jest podpięty przez `<script src>` w renderze —
  inaczej usunięcie tagu nie wywali żadnego testu, a przełącznik przestanie
  działać
- w `base.html` **nie ma już** handlera `/` (dowód likwidacji duplikatu)

Analogiczna asercja **nie ma sensu dla `nawigacja.js`**: moduł trafia do
`dist/cytoscape-bundle.js` przez import w `controls.js` (entry
`js/cytoscape-entry.js`, esbuild), więc w renderze `graf.html` nie pojawi
się osobny `<script src>` — tag bundla (`graf.html:202`) istnieje już dziś
i niczego z tej iteracji nie broni. Dla grafu rolę tę pełnią testy vitest
samego modułu plus test Playwright klikający przycisk.

**Playwright** — `src/integration_tests/`, obok istniejącego
`test_siec3d_bez_webgl.py` (jedyny dotychczasowy test przeglądarkowy
wizualizacji powiązań; testy widoków grafu bez przeglądarki żyją w
`src/powiazania_autorow/test_views.py`).

Graf:
- klik w „dopasuj" zmienia zoom/pan grafu
- Tab dochodzi do kontenera grafu, strzałka przesuwa widok
- `Tab` po sfokusowaniu grafu **wychodzi** z niego (brak pułapki, 2.1.2)

Skrót `/` — **to jest test broniący celu całej części A**, bez niego
usunięcie warunku z handlera nie wywali niczego:
- przy domyślnej preferencji `/` otwiera wyszukiwarkę globalną
- po kliknięciu przełącznika w stopce `/` **nie** otwiera wyszukiwarki
- po ponownym kliknięciu otwiera znowu
- przy wyłączonych skrótach baner podpowiedzi się nie pokazuje
- `/` wciśnięty przy focusie w polu tekstowym wpisuje znak, nie otwiera
  wyszukiwarki (zachowanie zastane, nie może się zepsuć)

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

**Nakładka może zasłonić graf na wąskich ekranach.** Przyciski zajmują prawy
dolny róg — jedyny wolny — więc przy małej wysokości widoku mogą przykryć
węzły. Mitygacja: półprzezroczyste tło jak w legendzie, `z-index` spójny z
sąsiadami (1001).

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
