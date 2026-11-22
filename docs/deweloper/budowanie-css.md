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
   `motyw-kompilator` (`docker/motyw-kompilator/serwer.js`, Node, te same
   pliki JS w kontekście `vm`), wołany przez `bpp/motyw_kompilator.py`
   (`DJANGO_BPP_MOTYW_KOMPILATOR_URL`; w dev bez tej zmiennej — jednorazowe
   `node serwer.js --jednorazowo`). Wynik trafia do modelu `MotywWlasny`
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
