# CSS/SCSS Build System

## Build Commands

- `grunt build` - Build all SCSS themes and collect static files
- `grunt watch` - Watch SCSS files for changes and rebuild automatically

**If you change any SCSS files, remember to run `grunt build` after.**

## Theme Files (Color Schemes)

Three theme files in `src/bpp/static/scss/`:

| Theme File | Primary Color |
|------------|---------------|
| `app-blue.scss` | `#1779ba` (Foundation default) |
| `app-orange.scss` | `#f26621` |
| `app-green.scss` | `green` |

Each theme imports: settings -> common.scss -> components -> Foundation framework.

## Common.scss

Location: `src/bpp/static/scss/common.scss`

Central style repository importing: `left_menu`, `top_bar`, `base_footer`,
`search_banner`, `praca_detail`, `uczelnia`, `jednostka`, `flash_messages`,
`komparator_pbn`, `ewaluacja_metryki`, `ewaluacja_optymalizacja`,
`_support_button`.

Also contains: external link styling, multiseek reports, Select2,
discipline colors, print styles.

## Key Component Files

Location: `src/bpp/static/scss/`
- `top_bar.scss` - Navigation header and dropdown menus
- `browse*.scss` - Browse page styles
- `checkbox.scss` - Form controls

## Icon System - Foundation Icons

Icons use `fi-*` classes. **Navigation menu icons require explicit sizing
in `top_bar.scss`:**

```scss
.top-bar .dropdown.menu {
    .menu.vertical .fi-icon-name {
        font-size: 1.6rem;
        margin-right: 0.8rem;
    }
}
```

When adding new icons to menus, add them to the selector list in
`top_bar.scss` (lines 389-426).

## Menu górne: mysz i dotyk

Rozwijane menu paska (`top_bar.html`) ma dwie ścieżki otwierania:

- **mysz** — `:hover` plus skrypt `src/bpp/static/bpp/js/top-bar-menu.js`
  (pokazanie od razu, schowanie po 500 ms od zjechania kursorem);
- **dotyk** — klasa `is-active` na pozycji. Zwykłe podmenu (`li > ul`)
  obsługuje Foundation DropdownMenu, bloki wielokolumnowe
  (`li.has-submenu > .menu-columns-wrapper`) — `top-bar-menu.js`, bo
  Foundation widzi tylko podmenu będące listą `<ul>`.

Reguły `:hover`, które **otwierają** podmenu, pisz w mixinie
`tylko-z-kursorem` (`@media (hover: hover)`) z `top_bar.scss`. Na telefonie
„najechanie” po stuknięciu zostaje na elemencie do następnego stuknięcia
w coś klikalnego, więc podmenu otwartego samym `:hover` nie da się tam
zamknąć. Każdy stan otwarcia musi mieć odpowiednik z klasą `is-active`.

Na telefonie (≤ 639 px) blok wielokolumnowy zajmuje całą szerokość paska.
Na dotyku podmenu wyższe niż ekran przewija się w środku
(`--bpp-podmenu-max` ustawia skrypt) — na szerokim ekranie pasek jest
przyklejony, więc nie przewinie się ze stroną.

Menu modułu redagowania (`admin-menu.css`) otwiera `:hover` albo klasa
`over`; na dotyku przełącza ją `src/bpp/static/bpp/js/admin-menu-dotyk.js`.

Testy: `src/integration_tests/test_top_bar_menu_dotyk.py`,
`test_top_bar_menu_hover.py`, `test_admin_menu_dotyk.py`.

## Scroll Offset for Sticky Navigation

The public frontend has TWO sticky elements at the top:
- `nav.sticky-header` - main navigation bar (variable height)
- `#breadcrumbs-wrapper` - breadcrumb bar below nav (also sticky)

Django admin has its own sticky header + breadcrumbs.

When implementing scroll-to-element, ALWAYS use
`window.bpp.scrollToVisible(element)` (defined in
`src/bpp/static/bpp/js/bpp.js`) - it dynamically reads sticky
elements' height via `element.offsetHeight`.

`scrollIntoView({ block: 'start' })` alone is NOT sufficient -
it scrolls under the sticky bars. Never hardcode pixel offsets.

## Motywy z konfiguracji

Oprócz motywów pisanych ręcznie (`app-*.scss`) jest jeden ogólny motyw
sterowany konfiguracją: `src/bpp/static/scss/_app-konfig.scss`. Konfig to
płaski JSON z [konfiguratora wyglądu](../administrator/konfigurator-wygladu.md)
(kolory, czcionka, menu, przyciski). Schemat, walidację (w tym kontrast
WCAG), zamianę konfiga na punkt wejścia SCSS i tryb ciemny trzyma
`src/bpp/static/bpp/js/motyw-konfig.js`, a kompilację
`motyw-kompilator.js`. Używają ich przeglądarka, serwis kompilatora i Grunt,
więc podgląd i wynik są identyczne bajt w bajt.

`_settings.scss` ma przy kilku zmiennych `!default` (rozmiar tekstu, paleta,
tło, czcionka, zaokrąglenia, waga nagłówków, paleta przycisków). Punkt
wejścia z konfiga ustawia je przed importem. Dla `app-blue` nic się nie
zmienia.

Konfig trafia do CSS-a na dwa sposoby:

1. **Konfigurator → „Zastosuj”** (droga zwykła). Podgląd kompiluje
   przeglądarka (web worker `motyw-kompilator-worker.js`, dart-sass w czystym
   JS). Przy „Zastosuj” CSS buduje osobny, odizolowany serwis
   `motyw-kompilator` (gotowy obraz `node:22-alpine` uruchamiający
   `bpp/js/motyw-kompilator-serwer.js` z wolumenu plików statycznych, tylko
   do odczytu; te same pliki JS w kontekście `vm`), wołany przez
   `bpp/motyw_kompilator.py` (`DJANGO_BPP_MOTYW_KOMPILATOR_URL`; w dev bez
   tej zmiennej — jednorazowe `node motyw-kompilator-serwer.js
   --jednorazowo`). Po aktualizacji BPP serwis sam wczytuje nowe pliki
   (a przy zmianie samego serwera kończy się i Docker go wznawia). Wynik trafia do modelu `MotywWlasny`
   (jeden na uczelnię) i jest serwowany pod `/bpp/motyw-wlasny/<sha256>.css`
   z `Cache-Control: immutable`. Uczelnia dostaje `theme_name =
   "app-wlasny"`, a `bare.html` dołącza plik poza `{% compress %}`. Po
   aktualizacji BPP `manage.py odswiez_motywy` (entrypoint) przebudowuje
   motywy z zapisanych ustawień.
2. **Plik w repo**: `src/bpp/static/scss/motywy/<nazwa>.json`. Task Grunta
   `motywy` kompiluje go do `scss/app-<nazwa>.css`, a
   `django_bpp/motywy_z_konfiguracji.py` dopisuje motyw do `BPP_THEMES`.
   Nie trzeba targetu w `Gruntfile.js` ani wpisu w settings. Konfig
   z błędem (np. za mały kontrast) przerywa build.

Zasoby konfiguratora buduje Grunt (`build` i `build-non-interactive`):

- `shell:esbuildSass`: `bpp/js/dist/sass-przegladarka.js` (dart-sass dla
  przeglądarki, ok. 3,2 MB, 700 KB po gzipie; ładuje go tylko worker),
- `motywyZrodla`: `bpp/js/dist/motyw-zrodla-scss.json` (pliki
  `scss/*.scss` BPP oraz `scss/` i `_vendor/` Foundation; w obrazie nie ma
  `node_modules`).

Podgląd: strony w ramkach konfiguratora otwierane są z `?podglad_motywu=1`
(działa tylko dla obsługi). Zamiast motywu dostają pusty
`<style id="bpp-motyw-podglad">`, wypełniany synchronicznie z
`window.parent.BppKonfiguratorCss`, zanim ruszy JS Foundation. Foundation
odczytuje breakpointy z CSS-a przy starcie, więc później wstawiony CSS
dawałby układ telefonu na komputerze.

`_callouts.scss` (przez `common`) nadpisuje globalnie `$global-radius: 6px`;
`_app-konfig.scss` zapamiętuje wybrane zaokrąglenie w `$cfg-promien`
i przywraca je przed importem Foundation.

Spec: `docs/superpowers/specs/2026-11-22-konfigurator-wygladu-design.md`.

Testy: `tests/js/motyw-konfig.test.js` (vitest, z prawdziwą kompilacją),
`src/bpp/tests/test_konfigurator_wygladu.py`,
`src/django_bpp/tests/test_motywy_z_konfiguracji.py`.

## Tryb ciemny (każdy motyw; warianty `-auto` i `-ciemny`)

Każdy motyw ma wersję jasną i ciemną. Odwiedzający zawsze może przełączyć
się na tę drugą pigułką ☀ | ☾ na pasku menu (patrz niżej); wariant motywu
wybrany w polu „Motyw kolorystyczny” (`Uczelnia.theme_name`) decyduje tylko
o tym, co widać **bez** wyboru odwiedzającego (tryb domyślny):

| Motyw | Bez wyboru | Ciemne reguły pod |
|---|---|---|
| `app-X` | jasny — także przy ciemnym systemie (jak przed wprowadzeniem trybu ciemnego) | `@media screen` + `html:where([data-tryb-kolorow="ciemny"])` |
| `app-X-auto` | wg systemu/przeglądarki (`prefers-color-scheme`) | `@media screen and (prefers-color-scheme: dark)` + `html:where(:not([data-tryb-kolorow="jasny"]))` oraz `@media screen` + `html:where([data-tryb-kolorow="ciemny"])` |
| `app-X-ciemny` | ciemny (niezależnie od systemu) | `@media screen` + `html:where(:not([data-tryb-kolorow="jasny"]))` |

Na `-ciemny` pigułka pozwala więc wybrać wersję jasną — tak samo jak na
`app-X` ciemną: w każdym motywie pigułka przełącza między trybem domyślnym
a drugą wersją.

Warianty mają wszystkie motywy ręczne: `blue`, `green`, `orange`, `vizja`,
`mwsl`, `uafm` (np. `app-green-auto`, `app-green-ciemny`). Każdy motyw ma
treść w `_app-X-baza.scss`, a `app-X.scss`, `-auto` i `-ciemny` różnią się
tylko końcówką. Mixin dostaje `$primary-color` i `$drugi: $secondary-color`
(drugi akcent, np. ikony w kolorze dodatkowym).

Rozmiary (gzip): `app-X` ok. 62–63 KB (było 50–51 KB, przed dodaniem
ciemnych reguł pod pigułkę), `-ciemny` ok. 63 KB, `-auto` ok. 74–75 KB
(ciemne reguły dwa razy — wg systemu i z pigułki).

Wydruk jest zawsze jasny (ciemne reguły siedzą w `@media screen`).

### Pliki

- `_tryb-ciemny.scss` — paleta (`--tc-*` na `<html>`), funkcje kontrastu
  WCAG i mixin `bpp-tryb-ciemny($glowny, ...)`. Kolor akcentu (linki,
  aktywne elementy) jest wyliczany z `$primary-color` motywu tak, by miał
  kontrast >= 4.5:1 na ciemnych powierzchniach.
- `_tryb-ciemny-komponenty.scss` — selektory komponentów BPP i bloków
  `<style>` z szablonów z jasnym tłem / ciemnym tekstem / jasną ramką,
  przypisane do kolorów palety. Wygenerowane przez
  `bin/tryb-ciemny-selektory.py`, potem przejrzane ręcznie.
- `_app-blue-baza.scss` — treść motywu niebieskiego bez `@import "print"`;
  importują ją `app-blue.scss`, `app-blue-auto.scss`, `app-blue-ciemny.scss`.

Wszystkie reguły trybu ciemnego mają prefiks `html` (+1 do specyficzności),
dzięki czemu wygrywają z arkuszami dostawców ładowanymi po motywie
(select2, jQuery UI, multiseek) i z blokami `<style>` w szablonach. Style
inline (`style="color: #666"`) nadpisują selektory atrybutów z `!important`
na końcu `_tryb-ciemny.scss`.

### Jak dodać ciemny wariant do kolejnego `app-*` (np. `app-green`)

1. Przenieś treść `app-green.scss` (bez końcowego `@import "print"`) do
   `_app-green-baza.scss`; `app-green.scss` zostaje jako
   `@import "app-green-baza"; @import "print";`. Sprawdź, że
   `app-green.css` kompiluje się identycznie jak przed zmianą (`cmp`).
2. Utwórz `app-green-auto.scss` i `app-green-ciemny.scss` na wzór
   niebieskich — różnią się tylko importem bazy. Mixin dostaje
   `$primary-color` motywu; w razie potrzeby podaj też inne argumenty
   (`$tlo`, `$pow`, …), np. lekko zabarwione tło.
3. Jeśli motyw ma własne nadpisania z jasnymi kolorami (np.
   `.select2-results__option--highlighted` w `app-green.scss`), dopisz
   ich ciemne odpowiedniki — najprościej w bloku `@media` w pliku
   `-auto`/`-ciemny` po `@include`.
4. Dodaj cele `sass:<motyw>_auto` / `sass:<motyw>_ciemny` w `Gruntfile.js`
   (sekcja `sass` i lista `concurrent.themes`) i wpisy w `BPP_THEMES`
   (`src/django_bpp/settings/base.py`). Bez migracji — pole nie ma `choices`.
5. Dopisz motywy do `CIEMNE_WARIANTY` w `src/bpp/tests/test_tryb_ciemny.py`.
6. Uruchom `run-site`, ustaw uczelni nowy motyw i odpal audyt (niżej).

### Audyt: białe plamy i kontrast

`bin/tryb-ciemny-audyt.py` otwiera ~25 stron/stanów (lista, szczegóły,
multiseek z wynikami, raporty, formularze, rozwinięte menu, okno
wyszukiwania, rozwinięty autocomplete, logowanie) w Playwright z
`color_scheme="dark"` i zgłasza:

- **plamy** — widoczne elementy > 40×40 px z tłem o luminancji > 0.8,
- **kontrast** — tekst o kontraście z efektywnym tłem < 4.5:1 (3:1 dla
  dużego tekstu).

```bash
uv run python bin/tryb-ciemny-audyt.py --wyjscie /tmp/audyt          # desktop
uv run python bin/tryb-ciemny-audyt.py --mobile --wyjscie /tmp/audyt-m
uv run python bin/tryb-ciemny-audyt.py --strony autor,publikacja --szczegoly
```

Port i token czyta z `.dev_helpers_*` (działający `run-site`). W katalogu
`--wyjscie` lądują zrzuty i `raport.json`. Nowy komponent z jasnym tłem?
Najpierw sprawdź, czy wystarczy odświeżyć listę generatorem:

```bash
npx sass --no-source-map -q \
    --silence-deprecation=import,global-builtin,if-function \
    --load-path=node_modules/foundation-sites/scss \
    src/bpp/static/scss/app-blue.scss /tmp/app-blue.css
uv run python bin/tryb-ciemny-selektory.py --szablony /tmp/app-blue.css
```

Wynik (mixin `bpp-tryb-ciemny-komponenty`) wklej w miejsce mixinu w
`_tryb-ciemny-komponenty.scss`, przejrzyj diff, przebuduj i powtórz audyt.
Przypadki szczególne (przyciski z kolorowym tłem, ciemne wypełnienia
wykresów, style inline) dopisuj ręcznie w `bpp-tryb-ciemny-reguly`.
Test `test_tryb_ciemny_bez_bialych_plam` (Playwright) pilnuje kilku stron.

### Style spoza CSS motywu: zmienne `--bpp-*`

Bloki `<style>` w szablonach, osobne arkusze modułów (np.
`ewaluacja_optymalizuj_publikacje.css`) i style ustawiane z JS **nie
przechodzą** ani przez mixin `bpp-tryb-ciemny`, ani przez `przetworzCss`
konfiguratora — w trybie ciemnym zostają jasne. Dla nich są zmienne kolorów
z kolorem zapasowym:

```css
background: var(--bpp-tlo-pow-2, #f8f9fa);
color: var(--bpp-tekst-przygaszony, #6c757d);
```

W trybie jasnym zmienne nie istnieją (zostaje kolor zapasowy — wygląd bez
zmian), w ciemnym definiują je oba mechanizmy: `_tryb-ciemny.scss` (blok
`--bpp-*` w mixinie) i `ZMIENNE_KOLOROW` w `motyw-konfig.js`. Lista:
`--bpp-tlo-pow`, `-pow-2`, `-hover`, `-sukces`, `-ostrzezenie`, `-blad`,
`-info`, `--bpp-ramka`, `--bpp-tekst`, `-przygaszony`, `-sukces`,
`-ostrzezenie`, `-blad`, `--bpp-akcent`. Test
`test_zmienne_kolorow_zdefiniowane_w_obu_trybach_ciemnych` pilnuje, żeby
każda użyta zmienna była zdefiniowana w obu miejscach.

Zamianę robi `bin/tryb-ciemny-zmienne.py PLIK…` (pliki `.html` — bloki
`<style>` i atrybuty `style="…"`; obsługuje zagnieżdżenia SCSS; plakietki
i barwne gradienty skal zostawia). Wynik przejrzyj w `git diff`. Przepuszczone
są nim arkusze modułów (`src/*/static/*/scss/*.scss` poza motywem i adminem,
`deduplikator_publikacji.css`) oraz szablony z kolorami (bez admina, wydruków
i PDF-ów oraz samodzielnych stron bez motywu). **Nowy kolor w stylu modułu
albo szablonu** — pisz od razu `var(--bpp-…, kolor)` albo przepuść plik przez
narzędzie.

Audyt modułów: `bin/tryb-ciemny-audyt.py --moduly` (strony z menu + lista
`MODULY_DODATKOWE`) albo `--tylko-moduly`.

Wykresy JS (Plotly, circle-progress) w metrykach biorą kolory z wyliczonego
stylu strony: `ewaluacja_metryki/js/wykresy-motyw.js` owija
`Plotly.newPlot` i `$.fn.circleProgress` i — tylko gdy tekst strony jest
jasny — ustawia przezroczyste tło, kolor tekstu i siatki. Działa dla obu
mechanizmów trybu ciemnego bez znajomości palety.

Audyt (`bin/tryb-ciemny-audyt.py`) sprawdza też wiersze tabel w stanie
`:hover` (wpisy `HOVER`), tekst SVG (`fill`) i jasne tło wykresów SVG.
Zawartości `<canvas>` nie ocenia.

### Przełącznik jasny/ciemny na pasku menu

Przy każdym motywie `top_bar.html` pokazuje
„pigułkę” ☀ | ☾ (`tryb_kolorow_pigulka.html`, dołączana dwa razy: pasek
tytułowy na telefonie, prawa strona paska menu na komputerze — z odstępem na
przycisk UserWay). Semantyka: `role="radiogroup"` z dwoma `role="radio"`
(zaznaczone = widoczny tryb; roving tabindex, strzałki przenoszą wybór,
Spacja/Enter na zaznaczonym przy wyborze ręcznym wraca do domyślnego).
Klik w drugą połówkę wymusza tryb; klik w połówkę trybu domyślnego albo
w wybraną ręcznie — wraca do domyślnego (bez wpisu w `localStorage`).

Tryb domyślny motywu (`jasny`/`ciemny`/`auto`) liczy
`tryb_kolorow_domyslny()` w `bpp/context_processors/config.py` (zwykły
motyw — jasny, `-auto`, `-ciemny`, motyw z konfiguratora wg „Trybu
kolorów”, motyw z `scss/motywy/*.json` wg pola `tryb_kolorow`) i wypisuje
w `<html data-tryb-domyslny>` (`bare.html`). Podświetlenie (suwak)
i obwódkę wyboru ręcznego liczy **sam CSS**
(`_tryb-kolorow-przelacznik.scss`: `data-tryb-domyslny`,
`data-tryb-kolorow`, `prefers-color-scheme`) — poprawne od pierwszej
klatki; JS ustawia tylko `aria-checked`, `tabindex`, `aria-label`, `title`.
Połówki i suwak to `ul.dropdown.menu > li > a` (bez `data-dropdown-menu`),
więc kolor napisów paska dają im reguły każdego motywu, a przezroczystości
są w `opacity` pseudoelementów (przetworzCss nie musi ich znać). Flagę
`TRYB_KOLOROW_PRZELACZNIK` liczy `przelacznik_trybu_kolorow()` — zawsze,
poza podglądem konfiguratora i przymiarką.

- Wybór trzyma `localStorage` (`bpp-tryb-kolorow`); krótki skrypt w `<head>`
  `bare.html` (przed CSS — bez mignięcia) ustawia
  `<html data-tryb-kolorow="jasny|ciemny">`; brak atrybutu = jak system.
  Kliknięcia obsługuje `bpp/js/tryb-kolorow.js`.
- CSS: korzenie ciemnych reguł — tabela w sekcji „Tryb ciemny” wyżej.
  W SCSS to parametr `$korzen` mixinu `bpp-tryb-ciemny` (patrz
  `app-blue.scss`, `app-blue-auto.scss`, `app-blue-ciemny.scss`),
  w konfiguratorze — `KORZEN_AUTO`/`KORZEN_CIEMNY` w `przetworzCss`
  (tryb „jasny”: jasny CSS + ciemne reguły pod `KORZEN_CIEMNY`;
  „automatyczny”: pod oboma; „ciemny”: pod `KORZEN_AUTO` bez media query).
  Podgląd konfiguratora (`trybPodgladu`) dostaje jedną wersję, bez reguł
  pigułki. `:where()` nie dodaje specyficzności, więc reguły zachowują się
  jak pod zwykłym `html`. Wydruk zawsze jasny.
- Koszt: ciemne reguły są w CSS dwa razy. `app-blue-auto.css`: 382 KB →
  577 KB (gzip 61 KB → 76 KB); motyw z konfiguratora w trybie
  automatycznym ok. 412 KB → 605 KB (gzip 67 KB → 85 KB).
- Motyw z konfiguratora w trybie „jasny” i „ciemny” też ma teraz ciemne
  reguły obok jasnych (ok. +50% CSS, jak „automatyczny” bez drugiej kopii).
  Zastosowane motywy klientów przebuduje `odswiez_motywy` przy starcie
  kontenera po aktualizacji.
- Audyt z wymuszonym wyborem: `bin/tryb-ciemny-audyt.py --jasny
  --przelacznik ciemny` (system jasny, wybrany „Ciemny”) — dla zwykłego
  motywu powinien dać to samo co `-ciemny`.
