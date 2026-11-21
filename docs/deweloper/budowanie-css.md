# CSS/SCSS Build System

## Build Commands

- `grunt build` - Build all SCSS themes and collect static files
- `grunt watch` - Watch SCSS files for changes and rebuild automatically

**If you change any SCSS files, remember to run `grunt build` after.**

## Theme Files (Color Schemes)

Theme files in `src/bpp/static/scss/` (the list offered in the admin lives
in `BPP_THEMES` in `src/django_bpp/settings/base.py`):

| Theme File | Settings | Primary Color |
|------------|----------|---------------|
| `app-blue.scss` | `_settings.scss` | `#1779ba` (Foundation default) |
| `app-orange.scss` | `_settings_orange.scss` | `#f26621` |
| `app-green.scss` | `_settings_green.scss` | `green` |
| `app-vizja.scss` | `_settings_vizja.scss` | `#efa402` |
| `app-mwsl.scss` | `_settings_mwsl.scss` | `#e35b00` |
| `app-uafm.scss` | `_settings_uafm.scss` | `#b41906` |
| `app-apoz.scss` | `_settings_apoz.scss` | `#0073a6` (brand `#009ee0` darkened for WCAG AA), gold `#b99a4b` secondary |

Each theme imports: settings -> common.scss -> components -> Foundation framework.

### Adding a theme

1. `_settings_<name>.scss` (copy of an existing one) + `app-<name>.scss`
   (entrypoint, copy of an existing one).
2. Target `sass:<name>` in `Gruntfile.js` (both the `sass` section and
   `concurrent:themes`).
3. Entry in `BPP_THEMES` in `src/django_bpp/settings/base.py` — no migration
   needed (`Uczelnia.theme_name` has no `choices`).
4. Optional `--admin-hover-bg` colour in
   `src/django_bpp/templates/admin/base_site.html`.

`src/bpp/tests/test_admin/test_uczelnia_theme.py` checks that every theme in
`BPP_THEMES` has its SCSS file and Grunt target.

### Theme fonts (`app-apoz`)

`app-apoz` uses IBM Plex Sans (SIL OFL 1.1), self-hosted in
`src/bpp/static/bpp/fonts/ibm-plex-sans/` — `.woff2` files copied from the npm
package `@fontsource/ibm-plex-sans` 5.3.0 (latin + latin-ext subsets, weights
400/600/700, 400/700 italic; licence in `LICENSE.txt`). The `@font-face`
rules are generated in `app-apoz.scss`; no request goes to Google Fonts.

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
