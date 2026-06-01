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
