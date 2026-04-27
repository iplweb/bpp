# Migracja Foundation -> Tailwind v4

Status: **Etap 0 — fundament** (gałąź `feature/tailwind-migration`).

Ten dokument opisuje jak projekt przechodzi z Foundation Sites 6.9 na
Tailwind CSS v4. Migracja jest **etapowa** — Tailwind i Foundation
**współistnieją** dopóki ostatni szablon używający klas Foundation nie
zostanie zmigrowany. Dopiero wtedy usuwamy Foundation z `package.json`.

## Stan obecny (etap 0)

- Tailwind v4 (`tailwindcss@^4.1`, `@tailwindcss/cli@^4.1`) podpięty do
  Grunta jako trzy taski: `shell:tailwindBlue`, `shell:tailwindGreen`,
  `shell:tailwindOrange`. `concurrent:tailwind` uruchamia je równolegle.
- Wynikowe pliki: `src/bpp/static/tailwind/dist/{blue,green,orange}.css`.
- `bare.html` ładuje `TAILWIND_THEME_NAME` (nowy context var,
  `tailwind/dist/<color>.css`) **po** Foundation theme. Kolejność jest
  ważna — Tailwind `@layer components` ma nadpisywać Foundation tam, gdzie
  oba definiują tę samą klasę.
- Alpine.js 3 załadowany przez `bundle-entry.js`. Auto-startuje się na
  `DOMContentLoaded`, więc `x-data`/`x-show` w szablonach po prostu
  działają.
- Foundation JS (`$(document).foundation()`) **dalej działa**. Migracja JS
  idzie razem z migracją CSS w danym widoku.

## Nazewnictwo i tokeny

`src/bpp/static/tailwind/_theme-base.css` deklaruje wspólne tokeny
(neutrals, breakpoints, typografia, layout) skopiowane z
`src/bpp/static/scss/_settings.scss`. Per-theme entry points
(`blue.css`, `green.css`, `orange.css`) nadpisują paletę
primary/secondary z `_settings_*.scss`. Jeżeli zmieniasz tokeny w
Foundation `_settings.scss` — odzwierciedl zmianę w
`_theme-base.css` lub odpowiedniej theme entry.

Mapowanie breakpoints (Foundation -> Tailwind):

| Foundation | Tailwind   | px      |
|------------|------------|---------|
| `small`    | `sm:`      | 0       |
| `medium`   | `md:`      | 640px   |
| `large`    | `lg:`      | 1024px  |
| `xlarge`   | `xl:`      | 1200px  |
| `xxlarge`  | `2xl:`     | 1440px  |

Mapowanie palety:

| Foundation klasa | Tailwind utility   | CSS var               |
|------------------|--------------------|-----------------------|
| `.primary`       | `bg-primary`       | `--color-primary`     |
| `.secondary`     | `bg-secondary`     | `--color-secondary`   |
| `.success`       | `bg-success`       | `--color-success`     |
| `.warning`       | `bg-warning`       | `--color-warning`     |
| `.alert`         | `bg-alert`         | `--color-alert`       |

## Compat layer

`src/bpp/static/tailwind/_components.css` re-implementuje warstwę
najczęściej używanych komponentów Foundation jako Tailwind
`@layer components`. Pokrywa:

- `.button` (warianty: secondary/success/warning/alert/hollow,
  rozmiary: tiny/small/large/expanded, stany: disabled)
- `.callout` (warianty primary/secondary/success/warning/alert,
  rozmiary small/large)
- `.label` (warianty)
- `.badge` (warianty)
- `.close-button`

Dzięki temu istniejące szablony używające `class="button success"` czy
`class="callout warning"` **nadal renderują się poprawnie** — tyle, że
przez Tailwind, a nie Foundation. Pozwala to na stopniowe migrowanie
HTMLa bez breaking changes.

Komponenty rzadziej używane (accordion, tabs, dropdown, reveal,
top-bar, magellan, sticky, off-canvas, switch, tooltip) **nie są w
compat layer**. Przy migracji szablonu, który z nich korzysta:
1. Sprawdź czy istnieje partial w `src/django_bpp/templates/components/`
   (button.html, callout.html, modal.html...)
2. Jeśli tak — `{% include %}`.
3. Jeśli nie — napisz Tailwind+Alpine, dodaj partial dla wielokrotnego
   użycia.

## Foundation JS -> Alpine.js mapping

| Foundation             | Alpine.js zamiennik                                  |
|------------------------|------------------------------------------------------|
| `data-reveal` (modal)  | `components/modal.html` (x-data, x-show, x-on)       |
| `data-accordion`       | `x-data="{open:false}"` + `x-show` na content        |
| `data-toggle`          | `x-data="{open:false}"` + click toggle               |
| `data-dropdown-menu`   | `x-data` + `x-on:mouseleave`/`x-on:click.outside`    |
| `data-closable` (call) | `components/callout.html` z `closable=True`          |
| `data-sticky`          | CSS `sticky top-0` (Tailwind utility)                |
| `data-magellan`        | IntersectionObserver + Alpine binding                |
| `data-equalizer`       | CSS Grid lub Flexbox (już bez JS)                    |

Komponenty Foundation JS, które zostają **bez zmian** dopóki
nie zmigrujesz konkretnego widoku:
- Inicjalizacja `$(document).foundation()` w `bare.html` zostaje.
- Custom JS w `top_bar.html` (470 linii) — to do osobnej migracji.

## Zewnętrzne zależności jQuery

**Zostają** (Tailwind v4 / Alpine z nimi nie kolidują):

- `select2` + `select2-foundation-theme` — wymagają jQuery
- `datatables.net` + `datatables.net-zf` — wymagają jQuery, theme zostaje
- `jqueryui` (drag/drop, datepicker)
- `foundation-datepicker` — używa jQuery, ale to nie Foundation 6 JS
- `jquery-circle-progress`, `jinplace`

Etap 3+ migracji rozważy ich zamianę, ale nie jest to blocker do
wymiany Foundation 6 CSS/JS.

## Jak migrować pojedynczy szablon

1. **Branch off**: `git checkout -b migrate/<obszar>` z
   `feature/tailwind-migration`.
2. **Przejrzyj** szablon — wypisz użyte klasy Foundation (`.row`,
   `.columns`, `.medium-6`, `.button.success`, `.callout`, ikony `fi-*`...)
   i komponenty JS (`data-reveal`, `data-accordion`...).
3. **Wymień klasy gridowe**:
   - `<div class="row">` -> `<div class="max-w-3xl mx-auto px-4">`
   - `<div class="columns medium-6 large-8">` ->
     `<div class="md:w-1/2 lg:w-2/3">`
   - `<div class="grid-x grid-padding-x">` -> `<div class="flex flex-wrap -mx-4">`
   - `<div class="cell medium-6">` -> `<div class="md:w-1/2 px-4">`
   - `text-center`/`text-right`/`text-left` — działają identycznie w Tailwind
4. **Zamień komponenty Foundation JS** wg tabeli wyżej. Jeśli w
   `templates/components/` jest gotowy partial — użyj `{% include %}`.
5. **Sprawdź wizualnie** w przeglądarce w 3 motywach (DJANGO_BPP_THEME_NAME=
   app-blue / app-green / app-orange).
6. **Nie usuwaj** klas Foundation typu `.button` na chwilę — compat
   layer i Foundation oba je obsługują, ale przy migracji **preferuj**
   Tailwind utilities (`bg-primary text-white px-4 py-2 ...`) zamiast
   klasy Foundation. To jest ten "gradual switch".
7. **Test**: jeśli widok ma testy Playwright — uruchom je. Inaczej
   smoke-testuj klikalnie.
8. **Commit**: `migrate(<obszar>): replace Foundation classes with Tailwind`.

## Build i dev

```bash
# pełny build (SCSS + Tailwind + JS bundle + collectstatic)
grunt build

# tylko Tailwind (szybkie iteracje na CSS)
grunt tailwind

# watch mode — odbudowuje SCSS i Tailwind przy zmianach
grunt watch
```

Output Tailwinda: `src/bpp/static/tailwind/dist/{blue,green,orange}.css`.
collectstatic je przenosi do `STATIC_ROOT/tailwind/dist/...`.

## Następne etapy (roadmapa)

Etapy są niezależnymi PR-ami opartymi o tę gałąź.

- **Etap 1**: `bare.html`, `base.html`, `top_bar.html` — wymiana
  Foundation grid + custom JS dropdown menu.
- **Etap 2**: strona główna i `browse/` — `wydzial.html` (Magellan +
  sticky), karty jednostek/autorów.
- **Etap 3**: formularze (`crispy_forms` rendering) i flash messages
  (`base.html` -> Alpine callout).
- **Etap 4**: `multiseek/` (formularz wyszukiwania), tabele wyników.
- **Etap 5**: szczegóły pracy (`praca_detail.html`), profil autora.
- **Etap 6**: panele administracyjne *poza* Django admin (operacje,
  importy, ewaluacja).
- **Etap 7**: ikony — `fi-*` (1551 wystąpień) na Heroicons albo Tabler
  Icons (SVG).
- **Etap 8**: usunięcie Foundation z `package.json`, czystka SCSS,
  usunięcie compat layer (jeśli zostały tam tylko nieużywane klasy).

## Why not Vite?

Rozważone. Ostatecznie odrzucone w etapie 0 z powodu:

- esbuild już bunduje JS przez Grunta — Vite nic nie zyska na JS.
- Tailwind v4 CLI jest stand-alone i wystarczy. PostCSS plugin nie
  potrzebny.
- Vite wymagałby przebudowy `bundle-entry.js`, `bare.html` (HTML import
  maps lub `vite_django` integration) i Dockerfile.
- Coexistence z Gruntem przez kilka miesięcy jest prostsze przy
  obecnym stacku.

Wracamy do tematu Vite po zakończonej migracji Foundation -> Tailwind,
jako osobne refactoring.
