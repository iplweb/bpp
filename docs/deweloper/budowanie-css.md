# CSS/SCSS Build System

## Build Commands

- `grunt build` - Build all SCSS themes and collect static files
- `grunt watch` - Watch SCSS files for changes and rebuild automatically

**If you change any SCSS files, remember to run `grunt build` after.**

## Theme Files (Color Schemes)

Pliki motywów w `src/bpp/static/scss/` (listę oferowaną w adminie uczelni
trzyma `BPP_THEMES` w `src/django_bpp/settings/base.py`):

| Motyw | Ustawienia | Kolor główny |
|-------|------------|--------------|
| `app-blue.scss` | `_settings.scss` | `#1779ba` (domyślny Foundation) |
| `app-orange.scss` | `_settings_orange.scss` | `#f26621` |
| `app-green.scss` | `_settings_green.scss` | `green` |
| `app-vizja.scss` | `_settings_vizja.scss` | `#efa402` |
| `app-mwsl.scss` | `_settings_mwsl.scss` | `#e35b00` |
| `app-uafm.scss` | `_settings_uafm.scss` | `#b41906` |
| `app-apoz.scss` | `_settings_apoz.scss` | `#0073a6` (przyciemniony `#009ee0` dla WCAG AA), drugorzędny złoty `#b99a4b` |

Each theme imports: settings -> common.scss -> components -> Foundation framework.

### Dodanie motywu

1. `_settings_<nazwa>.scss` (kopia istniejącego) + `app-<nazwa>.scss`
   (punkt wejścia, kopia istniejącego).
2. Target `sass:<nazwa>` w `Gruntfile.js` (sekcja `sass` i lista
   `concurrent:themes`).
3. Wpis w `BPP_THEMES` w `src/django_bpp/settings/base.py` — bez migracji
   (`Uczelnia.theme_name` nie ma `choices`).
4. Opcjonalnie kolor `--admin-hover-bg` w
   `src/django_bpp/templates/admin/base_site.html`.

`src/bpp/tests/test_admin/test_uczelnia_theme.py` sprawdza, że każdy motyw
z `BPP_THEMES` ma plik SCSS i target Grunta.

### Czcionka motywu `app-apoz`

`app-apoz` używa IBM Plex Sans (licencja SIL OFL 1.1), hostowanej lokalnie
w `src/bpp/static/bpp/fonts/ibm-plex-sans/` — pliki `.woff2` skopiowane
z paczki npm `@fontsource/ibm-plex-sans` 5.3.0 (podzbiory latin + latin-ext,
wagi 400/600/700 oraz kursywa 400/700; licencja w `LICENSE.txt`). Reguły
`@font-face` generuje pętla w `app-apoz.scss`; żadne zapytanie nie idzie do
Google Fonts.

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
