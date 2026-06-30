# Design: Widget osadzania listy publikacji (loader `<script src>`)

- **Data:** 2026-06-30
- **Zgłoszenie:** Freshdesk #411 ("Widget/kod do osadzania listy publikacji BPP
  na stronie www jednostki uczelnianej")
- **Status:** zaakceptowany design → przejście do planu implementacji

## Kontekst i problem

Od sierpnia 2025 (commit `79b2390fc`) strona autora
(`src/bpp/templates/browse/autor.html:363-581`) ma sekcję "Kod do osadzenia
publikacji na stronie WWW", która pokazuje **~90 linii samodzielnego
JavaScriptu** do skopiowania i wklejenia na zewnętrzną stronę. Snippet fetchuje
`/api/v1/recent_author_publications/{id}/` (CORS `*`) i renderuje listę z
hardkodowanymi stylami inline.

Wady obecnego podejścia ("copy the whole blob"):

1. **Brak ścieżki aktualizacji.** Po wklejeniu JS staje się zamrożoną kopią na
   cudzym serwerze. Zmiana API, fix renderowania, nowe pole — żadna z rozsianych
   kopii się nie zaktualizuje. To główny problem.
2. **Style na sztywno inline** — nie da się customizować bez ręcznej edycji bloba.
3. **Kruchość copy-paste** — 90 linii `<script>` w edytorze CMS/WYSIWYG łatwo się
   psuje.
4. **Brak wsparcia dla jednostek** — istnieje tylko dla autora; #411 dotyczy
   właśnie jednostek.

Dodatkowo instancje serwują globalnie `x-frame-options: SAMEORIGIN`
(potwierdzone na `bpp.umlub.pl`), co czyni wariant iframe ze zgłoszenia
kosztownym i ryzykownym (clickjacking, zdejmowanie nagłówka per-URL). Wariant
loadera `<script>` ta polityka nie dotyczy.

## Rozwiązanie (skrót)

Zastąpić mechanizm "copy the blob" wzorcem **loader script** (`<script src>`) —
jeden hostowany, samokonfigurujący się plik JS, parametryzowany przez `data-*`,
obsługujący **autora i jednostkę**. Kod mieszka na serwerze BPP → fixy i nowe
funkcje docierają do wszystkich osadzeń naraz.

Na stronach autora/jednostki **nie pokazujemy już kodu** — drobny tekst z linkiem
do dokumentacji. Dokumentacja (MkDocs, GitHub Pages) staje się centrum:
interaktywny generator snippetu, tabela parametrów, lista klas CSS, **live
okienko** demonstracyjne.

## Architektura

### Komponent 1 — loader `bpp-publikacje.js`

- **Lokalizacja:** `src/bpp/static/embed/bpp-publikacje.js` + towarzyszący
  `src/bpp/static/embed/bpp-publikacje.css`.
- **Czysty vanilla JS, zero zależności.** Świadomie **nie** wchodzi do bundla
  grunt/esbuild — ma pozostać samodzielny i audytowalny.
- **Serwowany jako plik statyczny** pod stabilną, *niehashowaną* ścieżką
  `/static/embed/bpp-publikacje.js`.

Klient wkleja jedną linię:

```html
<script src="https://bpp.umlub.pl/static/embed/bpp-publikacje.js"
        data-autor="Kazimierz-Pasternak" data-limit="25" async></script>
```

Działanie loadera:

1. Odczytuje własny tag `<script>` (`document.currentScript`; fallback:
   `document.querySelector('script[src*="bpp-publikacje.js"]')` dla edge-case'ów).
2. Z `src` wyłuskuje **origin serwera BPP** → buduje URL-e API. Dzięki temu plik
   nie wymaga templatowania (stabilny, cacheowalny URL).
3. Czyta `data-*` z własnego taga.
4. Wstrzykuje **kontener tuż za swoim tagiem** (obsługa wielu widgetów na jednej
   stronie bez kolizji ID). Opcjonalny `data-target="#id"` dla jawnego
   umiejscowienia.
5. Jednorazowo, idempotentnie (guard przez flagę na `window` / sprawdzenie
   istnienia) dokłada `<link rel="stylesheet" href=".../bpp-publikacje.css">` —
   **chyba że** podano `data-no-css`.
6. `fetch` → API → render semantycznego HTML do kontenera.
7. Obsługa błędów: czytelny komunikat + link do profilu/strony w BPP.

> **Stabilny URL to twardy wymóg.** Jeśli projekt używa
> `ManifestStaticFilesStorage` (hashowane nazwy), snippet **musi** wskazywać
> ścieżkę niehashowaną; manifest-storage serwuje oryginał pod niehashowaną
> ścieżką (bez far-future cache, co tu jest pożądane — fix ma docierać). Plan
> implementacji weryfikuje to na realnej konfiguracji staticów.

### Komponent 2 — CSS `bpp-publikacje.css`

Minimalny, nieagresywny zestaw reguł pod klasami BEM. Klient nadpisuje własnym
CSS-em (wyższa specyficzność) lub całkowicie wyłącza przez `data-no-css`.

### Komponent 3 — API (`api_v1`)

Endpointy publiczne, read-only, z nagłówkami CORS jak dziś (`*`).

- **`recent_author_publications/<int:pk>/`** — **zostaje bez zmian** (wsteczna
  kompatybilność dla blobów wklejonych przed tą zmianą).
- Dokładamy **route slugowy** `recent_author_publications/<slug:slug>/`
  (slugi autorów nie są numeryczne → brak ambiguacji z route `<int:pk>`).
- Do obu route'ów dokładamy **opcjonalne** query params:
  `?limit=&rok_od=&rok_do=`. Brak paramów = dzisiejsze zachowanie
  (limit 25, bez filtra lat).
- **`recent_unit_publications/<int:pk>/`** oraz
  `recent_unit_publications/<slug:slug>/` — nowe, ten sam kształt JSON i te same
  query params.

**Semantyka publikacji jednostki:** rekordy z **jednostki ORAZ jej pod-jednostek
rekurencyjnie** (poddrzewo wydział → katedry → zakłady), `distinct`, sortowane
malejąco po roku (potem po dacie modyfikacji). Queryset **reużywa reguł
widoczności publicznego widoku jednostki** (nie surowy `Rekord`) — zgodnie z
ostrzeżeniem o niepublicznych danych z notatki w zgłoszeniu.

**Kształt odpowiedzi** (jak istniejący endpoint autora):

```json
{
  "autor_id": 11,            // lub "jednostka_id"
  "autor_nazwa": "...",      // lub "jednostka_nazwa"
  "count": 25,
  "publications": [
    {"id": "...", "opis_bibliograficzny": "...",
     "ostatnio_zmieniony": "...", "url": "https://..."}
  ]
}
```

### Komponent 4 — parametry `data-*` (kontrakt customizacji)

| Atrybut | Znaczenie | Domyślnie |
|---|---|---|
| `data-autor` **lub** `data-jednostka` | identyfikator encji — **slug lub ID** (dokładnie jeden z dwóch) | — (wymagany) |
| `data-serwer` | (opcjonalny) override origin BPP; domyślnie z `src` loadera | z `src` |
| `data-limit` | liczba pozycji | 25 |
| `data-rok-od` / `data-rok-do` | zakres lat | brak filtra |
| `data-styl` | `lista` \| `tabela` | `lista` |
| `data-no-css` | jeśli obecny — pomiń wstrzykiwanie domyślnego CSS | (CSS włączony) |
| `data-target` | selektor kontenera docelowego | (kontener tuż za tagiem) |

### Komponent 5 — strona autora / jednostki (UI)

- Z `browse/autor.html` **usuwamy** całą rozwijaną sekcję embed (linie 363-581:
  toggle, blok kodu, przycisk "Kopiuj", inline `<script>` z `toggleEmbedCode`/
  `copyEmbedCode`) wraz z powiązanym SCSS (`_autor-bem.scss:213-296`).
- W zamian **drobny tekst** (małe literki), np.:

  > 📄 Osadź publikacje tego autora na swojej stronie WWW — [kliknij tutaj](…)

- Link prowadzi do strony dokumentacji na GitHub Pages, **z kontekstem encji w
  query string**, aby generator w docs wypisał gotowy snippet:
  `https://iplweb.github.io/bpp/uzytkownik/widget-publikacji/?autor=Kazimierz-Pasternak&serwer=https://bpp.umlub.pl`
- Analogiczna linijka na stronie jednostki (`browse/jednostka.html`) z tekstem
  "…tej jednostki…" i `?jednostka=<slug>&serwer=<host>`.

Host (`request.scheme` + `request.get_host`) i slug encji template wstawia
server-side w link.

### Komponent 6 — dokumentacja (MkDocs Material)

Nowa strona `docs/uzytkownik/widget-publikacji.md` (+ wpis w nav w `mkdocs.yml`):

- **Po co to i jak osadzić** — wprowadzenie, jednolinijkowy snippet.
- **Interaktywny generator snippetu** — pola: serwer, autor (slug) / jednostka
  (slug), limit, zakres lat, styl, no-css. **Domyślne wartości:
  `serwer = https://bpp.umlub.pl`, `autor = Kazimierz-Pasternak`.** Zmiana pól →
  przeliczenie tekstu snippetu (pole do skopiowania) **oraz** live-podglądu.
  Czyta też query string (`?autor=`/`?jednostka=`/`?serwer=`), więc link ze
  strony BPP otwiera generator z już wstawioną encją.
- **Live okienko** — domyślny podgląd generatora to działający widget UM Lublin /
  autor Kazimierz Pasternak (renderowany na żywo przez ten sam loader).
- **Tabela parametrów `data-*`** (jak wyżej).
- **Tabela klas CSS** + przykład nadpisania (oficjalna "instrukcja
  customizacji").
- **Notki techniczne:** (1) obejście re-inicjalizacji loadera pod `document$`
  Material (`navigation.instant` nie odpala ponownie `<script>` w treści przy
  nawigacji SPA-like); (2) instancja w live-demo musi być HTTPS (docs są na
  HTTPS — inaczej mixed-content block); (3) live-demo zależy od uptime i wersji
  zewnętrznej instancji.

## Przepływ danych

1. Przeglądarka parsuje stronę hosta, napotyka
   `<script src="https://bpp.x/static/embed/bpp-publikacje.js" data-autor="..." ...>`.
2. Loader: odczyt własnego taga → origin z `src` → odczyt `data-*` →
   (opcjonalnie) wstrzyknięcie `<link>` CSS → utworzenie kontenera.
3. `fetch` → `https://bpp.x/api/v1/recent_author_publications/<slug>/?limit=&rok_od=&rok_do=`.
4. Render listy lub tabeli (wg `data-styl`) z klasami BEM do kontenera.
5. Błąd → komunikat + link do BPP.

## Klasy CSS (kontrakt)

```html
<div class="bpp-publikacje">
  <ol class="bpp-publikacje__lista">
    <li class="bpp-publikacje__item">
      <span class="bpp-publikacje__opis">…</span>
      <a class="bpp-publikacje__link">[szczegóły]</a>
    </li>
  </ol>
  <p class="bpp-publikacje__stopka">…</p>
</div>
```

Wariant `tabela`:

```html
<table class="bpp-publikacje__tabela">
  <tbody>
    <tr class="bpp-publikacje__wiersz">
      <td class="bpp-publikacje__opis">…</td>
      <td class="bpp-publikacje__link-cell"><a class="bpp-publikacje__link">…</a></td>
    </tr>
  </tbody>
</table>
```

Stan ładowania/błędu: `bpp-publikacje__loading`, `bpp-publikacje__error`.

## Bezpieczeństwo

- API pozostaje publiczne read-only z CORS `*` — ta sama postawa co dziś dla
  endpointu autora.
- Endpoint jednostki **reużywa reguł widoczności publicznego widoku jednostki**,
  nie surowy `Rekord`, żeby nie ujawnić niepublicznych danych.
- Loader nie wstrzykuje surowego HTML z niezaufanych źródeł poza
  `opis_bibliograficzny` (który już dziś zawiera `<b>`/`<i>` z BPP i jest tak
  renderowany przez istniejący blob); rendering trzyma się istniejącego
  kontraktu danych.
- **Subresource Integrity (SRI) — świadomie pomijamy.** Generyczna porada
  bezpieczeństwa każe dodać `integrity="sha384-..."` do `<script>`. Tutaj jest
  to przeciwskuteczne: cały sens loadera to **centralna aktualizacja** — każda
  zmiana `bpp-publikacje.js` zmieniłaby hash i zepsuła wszystkie osadzenia z
  przypiętym `integrity`. Dodatkowo skrypt jest **first-party** (ten sam origin
  co instancja BPP, której użytkownik i tak ufa i z której bierze dane przez
  API), a nie zewnętrzny CDN — model zagrożeń jest inny: kompromitacja serwera
  BPP i tak unieważnia korzyść z SRI na jego własnym pliku. Snippet generujemy
  więc **bez** `integrity`.

## Wsteczna kompatybilność

- Stary route `recent_author_publications/<int:pk>/` i jego domyślne zachowanie
  **nie zmieniają się** → blobi wklejone przed tą zmianą działają dalej.
- Nowe parametry query są opcjonalne i mają defaulty odtwarzające dzisiejsze
  zachowanie.

## Plan testów

- **API:**
  - autor: nowe params `limit`/`rok_od`/`rok_do` (w tym test, że brak paramów =
    zachowanie sprzed zmiany), route slugowy, `distinct`, 404.
  - jednostka: nowy endpoint — kształt JSON, filtry, **rekurencja po
    pod-jednostkach**, `distinct`, reguły widoczności, 404.
- **Template:** strona autora i jednostki zawiera nowy drobny link (z `?autor=`/
  `?jednostka=` + `serwer`), i **nie** zawiera już starego bloba/przycisku.
- **Playwright** (`src/integration_tests/`): smoke — strona testowa z loaderem na
  live-serwerze renderuje listę publikacji (lista i tabela; przypadek braku
  danych; błąd 404).

## Świadome decyzje (rozstrzygnięte w trakcie brainstormu)

- Zakres: loader + autor + jednostka, zastąpienie bloba autora.
- Parametry v1: encja, limit, zakres lat, styl, `data-no-css`, `tabela`.
- Identyfikator encji: **slug lub ID** (slug domyślny w generatorze/UX).
- Semantyka jednostki: **rekurencyjnie** (jednostka + pod-jednostki).
- Hosting loadera: **plik statyczny** w `/static/embed/`.
- Strona BPP: **bez bloba** — drobny link do dokumentacji.
- Dokumentacja: interaktywny **generator** + **live demo** (UM Lublin, autor 11
  / slug `Kazimierz-Pasternak`).

## Poza zakresem (v1)

- Statyczny export HTML/JSON ze zgłoszenia (wariant 3) — nie realizujemy.
- Wariant iframe — odrzucony (X-Frame-Options, gorsze wtapianie się, clickjacking).
- Paginacja po stronie widgetu — tylko `limit`; pełna lista pod linkiem do BPP.
- Czyszczenie/akumulacja cache hostowanego `embed.js` poza standardowymi
  nagłówkami staticów.
```

