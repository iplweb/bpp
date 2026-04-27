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

## Worked examples

Konkretne migracje już zrobione w tej gałęzi — kopiuj wzorzec.

### `base_footer.html` — pełna migracja małego szablonu

**Przed** (Foundation):

```html
<div class="cell">
    <div class="hide-for-print cell">
        <div class="footer__content">...</div>
    </div>
    <div class="show-for-print footer__print">
        <div class="text-right"><small>...</small></div>
    </div>
</div>
```

**Po** (Tailwind):

```html
<div class="w-full">
    <div class="w-full print:hidden">
        <div class="footer__content">...</div>
    </div>
    <div class="hidden print:block footer__print">
        <div class="text-right"><small>...</small></div>
    </div>
</div>
```

Co się stało linia-po-linii:
- `cell` (1× pełna szerokość) → `w-full`. `cell` w Foundation defaultuje
  do `flex: 0 0 auto; width: 100%`, a tu rodzicem jest `grid-x`
  (`flex flex-wrap`), więc `w-full` daje ten sam efekt. Po dalszej
  migracji rodzica można sprawdzić, czy `flex-none w-full` nie pasuje
  lepiej do oryginału.
- `hide-for-print` → `print:hidden` (Tailwind print modifier — ukrywa
  w `@media print`).
- `show-for-print` → `hidden print:block` (mobile-first: ukryte w
  screen, widoczne w print).
- BEM-classy (`footer__content`, `footer__print`, `footer__test-copyright`)
  oraz `text-right` zostają bez zmian — pochodzą z `base_footer.scss`
  (custom) i Foundation typography. Nie ma sensu ich migrować w tym
  kroku.

### `base.html` — `password_change_required` block

**Przed**:

```html
<div class="grid-x align-center">
    <div class="large-6 medium-8 small-12 cell">
        <div class="callout primary">Twoje hasło uległo przeterminowaniu...</div>
        <form>...</form>
    </div>
</div>
```

**Po**:

```html
<div class="flex flex-wrap justify-center">
    <div class="w-full md:w-2/3 lg:w-1/2">
        <div class="my-0 mb-4 p-4 border border-black/25 bg-primary/10 text-black">
          Twoje hasło uległo przeterminowaniu...
        </div>
        <form>...</form>
    </div>
</div>
```

Co się stało:
- `grid-x align-center` → `flex flex-wrap justify-center` (w Foundation
  XY Grid `align-center` to `justify-content: center`, mylnie sugeruje
  `align-items` ale to nie tak).
- `large-6 medium-8 small-12 cell` → `w-full md:w-2/3 lg:w-1/2`. Mobile-
  first: `small-12` to default 100%, w Tailwind `w-full`. `medium-8`
  (8/12 = 2/3) → `md:w-2/3`. `large-6` (50%) → `lg:w-1/2`. Pomijamy
  `cell` bo `w-full` już daje box-sizing: border-box i flex-wrap default.
- `callout primary` → utility classes pasujące do compat layer w
  `_components.css`: `my-0 mb-4 p-4 border border-black/25 bg-primary/10
  text-black`. Można alternatywnie użyć
  `{% include "components/callout.html" with variant="primary" body="..." %}`
  jeśli body to prosty string. Tutaj body to multiline z encodowanymi
  znakami specjalnymi, więc utility classes są wygodniejsze.

### `import_list_if/importlistifrow_list.html` — accordion (Foundation JS → Alpine)

**Przed**:

```html
<ul class="accordion" data-accordion data-allow-all-closed="true">
    <li class="accordion-item is-closed" data-accordion-item>
        <a href="#" class="accordion-title">Szczegóły operacji</a>
        <div class="accordion-content" data-tab-content>
            {% include "long_running/operation_details.html" %}
        </div>
    </li>
</ul>
```

**Po**:

```html
<ul class="my-4 list-none p-0" x-data="{ open: false }">
    <li class="border border-light-gray bg-white">
        <a href="#"
           @click.prevent="open = !open"
           :aria-expanded="open"
           class="relative block px-4 py-5 text-xs leading-none text-primary cursor-pointer hover:bg-light-gray">
            Szczegóły operacji
            <span class="absolute right-4 top-1/2 -translate-y-1/2 font-bold" x-text="open ? '–' : '+'"></span>
        </a>
        <div x-show="open" x-cloak class="border-t border-light-gray px-4 py-5">
            {% include "long_running/operation_details.html" %}
        </div>
    </li>
</ul>
```

Co się stało:
- `data-accordion` / `data-accordion-item` / `data-tab-content` /
  `data-allow-all-closed` — wszystkie hooki Foundation JS usunięte.
  Stan accordion-a kontroluje teraz `x-data="{ open: false }"`
  (zmienna boolean) plus `@click.prevent="open = !open"` na linku
  toggling.
- `is-closed` / `is-active` — Foundation classy stanu, zastąpione
  reaktywną zmienną `open`. Wariant "initially open" (`is-active`)
  to po prostu `x-data="{ open: true }"`.
- `accordion-title` → Tailwind utilities odtwarzające Foundation
  styling: `relative block px-4 py-5 text-xs leading-none text-primary
  cursor-pointer hover:bg-light-gray`. Indikator `+`/`–` przez
  `<span x-text="open ? '–' : '+'">`.
- `accordion-content` → `border-t border-light-gray px-4 py-5` plus
  `x-show="open" x-cloak`. `x-cloak` zapobiega flash-of-content
  przed hydratacją Alpine (CSS rule w `_components.css` ukrywa
  `[x-cloak]` aż Alpine je usunie).
- `:aria-expanded="open"` — accessibility binding, screen reader
  zna stan accordion.

Wzór do reuse: jednoelementowy accordion zawsze ma postać
`<wrapper x-data="{open:bool}">` + `<trigger @click="open=!open">` +
`<content x-show="open" x-cloak>`. Multi-item accordions z exclusive
opening: użyj `x-data="{ open: null }"` w wrapperze i sprawdzaj
`open === N` per item.

### Modal: Foundation `data-reveal` → Alpine x-show

Trzy warianty otwierania:

**Wariant 1 — modal i triggery w jednym x-data scope** (najczystszy,
gdy modal jest tuż przy triggerze, np. lista wierszy z przyciskami akcji).
Zob. `importer_autorow_pbn/main.html`:

```html
<div x-data="importerAutorowPbn">
    {% for row in rows %}
        <button @click="openIgnore('{{ row.id }}', '{{ row.name|escapejs }}')">Ignoruj</button>
    {% endfor %}

    <div x-show="ignoreModal" x-cloak
         x-on:keydown.escape.window="ignoreModal = false"
         class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/50" @click="ignoreModal = false"></div>
        <div class="relative bg-white border border-black/25 shadow-lg max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
            ...
        </div>
    </div>
</div>

<script>
document.addEventListener('alpine:init', () => {
    Alpine.data('importerAutorowPbn', () => ({
        ignoreModal: false,
        ignoreScientist: { id: '', name: '' },
        openIgnore(id, name) {
            this.ignoreScientist = { id, name };
            this.ignoreModal = true;
        },
        confirmIgnore() {
            // ... AJAX, then `this.ignoreModal = false`
        }
    }));
});
</script>
```

**Wariant 2 — modal otwierany przez window event** (gdy trigger jest w innym
template lub dynamicznie generowany przez JS). Zob.
`ewaluacja_optymalizuj_publikacje/optymalizuj_fixed.html`,
`ewaluacja_metryki/lista.html`, `pbn_import/dashboard.html`:

```html
<div x-data="{ open: false }"
     x-show="open" x-cloak
     x-on:keydown.escape.window="open = false"
     x-on:open-status-modal.window="open = true"
     x-on:close-status-modal.window="open = false"
     id="status-modal"
     class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="fixed inset-0 bg-black/50" @click="open = false"></div>
    <div class="relative bg-white border border-black/25 shadow-lg ...">
        ...
    </div>
</div>

<script>
function openTheModal() {
    window.dispatchEvent(new CustomEvent('open-status-modal'));
}
</script>
```

**Wariant 3 — generic `open-modal` event z `detail.id`** (gdy mamy
istniejący globalny handler typu `data-action="open-modal" data-modal-id=...`,
np. w `event-handlers.js`). Zob. `evaluation_browser.html`,
`import_dyscyplin/import_dyscyplin_detail.html`:

```html
<div x-data="{ open: false }"
     x-show="open" x-cloak
     x-on:open-modal.window="if ($event.detail.id === 'recalc-modal') open = true"
     x-on:close-modal.window="if ($event.detail.id === 'recalc-modal') open = false"
     id="recalc-modal" class="fixed inset-0 z-50 flex items-center justify-center">
    ...
</div>

<script>
// otwarcie z dowolnego miejsca:
window.dispatchEvent(new CustomEvent('open-modal', {detail: {id: 'recalc-modal'}}));
</script>
```

**Sticky modal** (nie zamykany przypadkowo) — pomija
`x-on:keydown.escape.window` i `@click="open=false"` na backdropie. Zob.
`evaluation_browser.html` (#recalc-modal podczas HTMX-driven recalculation).

### Tabs: Foundation `data-tabs` → Alpine x-data + active

Wzór z `pbn_import/session_detail.html` i
`import_dyscyplin/import_dyscyplin_detail.html`:

```html
<div x-data="{ active: 'panel1' }">
    <ul class="tabs">
        <li class="tabs-title" :class="{ 'is-active': active === 'panel1' }">
            <a href="#" @click.prevent="active = 'panel1'" :aria-selected="active === 'panel1'">Tab 1</a>
        </li>
        <li class="tabs-title" :class="{ 'is-active': active === 'panel2' }">
            <a href="#" @click.prevent="active = 'panel2'" :aria-selected="active === 'panel2'">Tab 2</a>
        </li>
    </ul>
    <div class="tabs-content">
        <div class="tabs-panel" :class="{ 'is-active': active === 'panel1' }" x-show="active === 'panel1'" id="panel1">
            ...
        </div>
        <div class="tabs-panel" :class="{ 'is-active': active === 'panel2' }" x-show="active === 'panel2'" id="panel2">
            ...
        </div>
    </div>
</div>
```

`x-show` ukrywa przez `display: none` (DOM zostaje), więc HTMX
`hx-trigger="load"` w panelach działa niezależnie od widoczności tabu.
DataTables i Select2 inicjalizowane w `$(document).ready` w panelach
nieaktywnych też działa — Alpine nie odmontowuje DOM.

Initial `active` można derive-ować z Django context:
`x-data="{ active: '{% if X %}panel1{% elif Y %}panel2{% else %}panel3{% endif %}' }"`.

### Dropdown: Foundation `data-toggle` → Alpine x-data + click-outside

Wzór z `ranking_autorow/results.html` i `multiseek/index.html`:

```html
<div x-data="{ open: false }">
    <button @click="open = !open" :aria-expanded="open" class="button dropdown-button">
        Inne formaty
    </button>
    <ul class="dropdown-content"
        x-show="open" x-cloak
        @click.outside="open = false"
        @keydown.escape.window="open = false">
        <li><a href="...">CSV</a></li>
        <li><a href="...">JSON</a></li>
    </ul>
</div>
```

`@click.outside` zamyka dropdown gdy user kliknie poza nim. ESC też zamyka.

### Pulapki

- **Multi-line `{# ... #}` NIE działają w Django** — to single-line
  syntax. Multi-line trzeba `{% comment %}...{% endcomment %}`. Inaczej
  komentarz leakuje do HTMLa jako tekst.
- **`{% verbatim %}` parsuje wszystko jako text** — nie da się włożyć
  `{% comment %}` wewnątrz verbatim block-u, bo tag nie zostanie
  zinterpretowany. Komentarze opisujące verbatim treść umieść **przed**
  `{% verbatim %}`.
- **`{% comment %}` nie może zawierać literalu `{% something %}`** w
  tekście — Django parser czasem traktuje to jako otwarcie tag-u i szuka
  match-ującego `{% endsomething %}`. Opisz w czystym tekście.
- **Alpine.js v3 obserwuje DOM** przez MutationObserver — nowe elementy
  z `x-data` dodane dynamicznie (Mustache, HTMX swap, jQuery `.html()`,
  `.append()`) **są automatycznie hydratowane**. Wyjątek: jeśli element
  jest dodany w `$(document).ready` przed Alpine.start(), trzeba upewnić
  się, że Alpine już wystartował (Alpine.start() w `bundle-entry.js` —
  bezpieczne).

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

## Status (commit-by-commit)

Gałąź `feature/tailwind-migration` zawiera już:

| # | Commit | Co zmigrowane |
|---|--------|---------------|
| 0 | setup Tailwind v4 + Alpine.js | infrastructure (config + compat layer + components partials + docs) |
| 1 | base_footer + password_change block | Foundation grid + visibility utilities |
| 2 | base.html grid wrappers | grid-container/grid-x/cell + Support button + test-server banner |
| 3 | import_list_if accordion | first Foundation JS → Alpine pattern (single-item accordion) |
| 4 | importer_autorow_pbn 4 modale | Alpine.data() pattern (state + AJAX in one component) |
| 5 | importer_autorow_pbn legacy grid | row/columns/large-N/medium-N → flex/w-full/md:w-1/2 |
| 6 | ewaluacja_optymalizuj status-modal | Foundation.Reveal direct API call → window event |
| 7 | 3 modale batch (lista, dashboard, evaluation_browser) | + sticky modal (recalc) + generic open-modal event |
| 8 | fix multi-line {# #} + 3 accordions (zrodlo, jednostka, deduplikator_autorow) | naprawione komentarze + wzór multi-item accordion |
| 9 | session_detail tabs | first Foundation tabs → Alpine x-data with active state |
| 10 | messageTemplate notifications | Alpine na Mustache-rendered DOM |
| 11 | step_fetch data-closable | ostatni `data-closable` w app templates |
| 12 | dropdowns (ranking_autorow, multiseek) | data-toggle/data-dropdown → Alpine + click-outside |
| 13 | deduplikator_zrodel + import_dyscyplin | accordion + tabs + modal w 2 plikach |

## Co jeszcze przed nami (roadmapa)

- **Etap A — `top_bar.html`** (470 linii custom JS dropdown menu).
  `data-dropdown-menu` + `data-responsive-toggle` + 6 sub-menusów z
  `data-submenu`. Wymaga porting do Alpine z zachowaniem: hover-show
  (desktop), tap-to-open (mobile), 500ms close timeout, keyboard nav,
  viewport-aware positioning. **HIGH RISK** — to navigation na każdej
  stronie. Wymaga wizualnej weryfikacji przed mergem.
- **Etap B — `browse/wydzial.html`** (data-magellan + data-sticky).
  Magellan to scrollspy nav + smooth scroll do anchor-ów. IntersectionObserver
  + Alpine binding zastąpi Foundation Magellan. Sticky → CSS `position: sticky`.
- **Etap C — `importer_publikacji/step_authors.html`** (HTMX-driven modal
  z Select2 + autocomplete-light). Alpine.js v3 powinien obsłużyć DOM
  po HTMX swap, ale modal jest re-tworzony per swap, więc Alpine init
  timing jest delikatny. Wymaga ostrożnej walidacji.
- **Etap D — pozostała siatka Foundation** w app templates (np.
  `praca_detail.html`, app-specific browse pages). Mechaniczna zamiana
  `row/columns/large-N/medium-N` → `flex/w-full/md:w-1/2` wedle wzoru
  z `importer_autorow_pbn/main.html`.
- **Etap E — Foundation icons fi-*** (1551 wystąpień) → Heroicons /
  Tabler Icons / inline SVG. Mechaniczna zamiana, ale duża powierzchnia.
- **Etap F — usunięcie Foundation**. Po zakończonej migracji wszystkich
  templates: `foundation-sites` z `package.json` + `bundle-entry.js`,
  `select2-foundation-theme` (zamiana na Tailwind theme dla Select2),
  `datatables.net-zf` → `datatables.net-dt`, czystka `_settings_*.scss`,
  redukcja compat layer w `_components.css` (zostaje tylko to co jeszcze
  używane lub usuwa się gdy wszystko zmigrowane).

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
