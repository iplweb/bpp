# djangoql-iplweb 0.25 query-UX in BPP — design

Date: 2026-06-04
Branch: `djangoql-query-ux` (worktree `~/Programowanie/bpp-djangoql-query-ux`)
Status: approved design, pending spec review

## Goal

Upgrade `djangoql-iplweb` in BPP from **0.23.0 → 0.25.0** and surface the new
query-UX features it ships, reusing the library's own primitives ("non-public"
endpoints / JS modules) as much as possible rather than reinventing them:

- **Syntax highlighting** of the DjangoQL query (token-colored overlay).
- **Error location highlighting** — the offending token / broken tail underlined
  with a red squiggle.
- **Multi-line** queries (Shift+Enter inserts a newline, Enter submits).
- **"Why 0 results"** breakdown (already in BPP) enriched with the upstream node
  roles, plus an **on-demand "Explain counts"** panel for any query.
- **Pretty-print / Format** button.
- **Better autocomplete** — value autocomplete inside `in (...)` lists (free
  with the new `completion.js`), existing `<fk>__rel` object pickers unchanged.

Surfaces: the public **"Szukaj zapytaniem"** view (`bpp:zapytanie`) gets the full
treatment; the **Django admin** gets highlight + multiline + auto explain-empty
via flags only (no Format/Explain buttons, no custom changelist template).

## Background — what 0.24/0.25 add (upstream)

All primitives live in the installed `djangoql` package (import name `djangoql`,
distribution `djangoql-iplweb`). Confirmed present in 0.25.0; absent in BPP's
current 0.23.0 venv.

Python:
- `djangoql.formatter.format_query(query, indent=2)` → pretty multi-line string;
  raises `DjangoQLError` on bad input. `serialize_node(node)` → compact form.
- `djangoql.breakdown.explain(queryset, search, schema=None, *, max_nodes=50)` →
  always-on per-node count tree `{text, count, role, children[, truncated]}`;
  `role ∈ {leaf, and, or, killer_and, dead_or_branch}`. `killer_and` = an AND
  whose result is 0 (where data runs out); `dead_or_branch` = a zero OR branch.
  `explain_empty(...)` is the lazy sibling (returns `None` unless 0 rows).
- `djangoql.queryset.apply_search` — already used by BPP.
- `djangoql.serializers.{DjangoQLSchemaSerializer, SuggestionsAPISerializer}` and
  `djangoql.views.SuggestionsAPIView` — already used by BPP for introspect /
  suggestions.

Static (shipped under `djangoql/static/djangoql/`):
- `js/completion.js` (`window.DjangoQL`; now bundles value-autocomplete inside
  `in (...)` and `object_reference` operator filtering).
- `js/multiline.js` (`window.DjangoQLMultiline`; auto-binds Shift+Enter on
  `textarea[name="q"], textarea.djangoql, textarea[data-djangoql]`; or
  `DjangoQLMultiline.enable(el)`).
- `js/highlight.js` (`window.DjangoQLHighlight`):
  - `tokenize(text)` → `[{type,value,start,end}]`.
  - `renderHtml(text[, errStart[, errEnd]])` → XSS-safe `<span class="dql-tok-…">`
    HTML (used to color breakdown node labels).
  - `attachOverlay(textarea)` → handle `{repaint, backdrop, setError(offset),
    setErrorAt(line,col), setErrorFrom(line,col), clearError()}`. One arg only.
    Keeps caret visible by copying the input text color to `caret-color`. Auto-
    inits on `textarea.djangoql-highlight`.
  - `offsetFromLineColumn(text, line, column)` (1-based → 0-based offset).
- `css/highlight.css` — structural rules + overridable palette via `--dql-*`
  custom properties (`--dql-name`, `--dql-operator`, …, `--dql-error-mark`).

Admin mixin `DjangoQLSearchMixin` (in `djangoql/admin.py`):
- New opt-in flag **`djangoql_highlight = False`** → adds `highlight.js` +
  `completion_admin_highlight.js` + `highlight.css` to `Media` and attaches the
  overlay to the admin search box.
- `multiline.js` is loaded **always** when completion is on.
- `djangoql_explain_empty = True` (default) → on a zero-row search the admin
  surfaces the breakdown as a `messages.WARNING` (template
  `djangoql/empty_breakdown.html`).
- Registers `…/format/` and `…/explain/` JSON endpoints, but **wires no Format /
  Explain buttons** into the admin UI by design (integrator's choice).

The canonical "wire it all by hand outside the admin" reference is
`djangoql-iplweb/example_project/` (`library/views.py`, `templates/library/
demo.html`, `static/library/js/demo.js`). BPP's public view mirrors that pattern.

## Current BPP state (pre-change)

- Pin: `pyproject.toml` `djangoql-iplweb>=0.23.0`; `uv.lock` pins 0.23.0.
- Schema: `src/bpp/djangoql_schema.py` — `BppQLSchema(RelPickerSchemaMixin,
  ExtrasSchema)`, auto-generates `<fk>__rel` `AutocompleteField` pickers
  (`lookup_name=<fk>`), visibility-filtered querysets, label fields. **Stable
  against 0.25 — no change expected** (the `lookup_name` kwarg it relies on is
  the iplweb feature shipped in 0.23.0).
- Public view: `src/bpp/views/zapytanie.py` (485 lines). `BppZapytanieSchema =
  BppQLSchema` alias. Server-rendered Run (Paginator), `explain_empty` + local
  `_annotate_breakdown` for the Polish "winowajca" 0-results panel, error shown
  as a `<pre>` callout. Endpoints: `bpp:zapytanie`,
  `bpp:zapytanie_introspect`, `bpp:zapytanie_suggestions`. Gated by
  `WprowadzanieDanychOrSuperuserMixin` (superuser or staff in
  `GR_WPROWADZANIE_DANYCH`). Template `bpp/zapytanie.html` (920 lines) with the
  bespoke ~130-line popup-repositioning IIFE + Tab shim coupled to 0.23
  internals, plus `bpp/_zapytanie_breakdown.html` partial.
- Admin: 9 classes set `djangoql_schema = BppQLSchema` (wydawca, zrodlo, autor,
  autor_dyscyplina, jednostka, patent, praca_doktorska base, wydawnictwo_ciagle,
  wydawnictwo_zwarte); 3 more use `DjangoQLSearchMixin` with the default schema /
  `enabled_by_default=False` (pbn_api PublicationAdmin, zglos_publikacje,
  rozbieznosci). `djangoql` is in `INSTALLED_APPS`; BPP serves the prebuilt
  djangoql static (no custom djangoql bundle), cache-busted by
  `TolerantManifestStaticFilesStorage`. Existing CSS patch
  `src/bpp/static/bpp/css/fix-djangoql-css-for-grappelli.css`.
- Tests: `src/bpp/tests/test_zapytanie.py` (pytest style; access control,
  query matching, error cases, `__rel` pickers, suggestions, breakdown).

## Design

### 1. Dependency bump

- `pyproject.toml`: `djangoql-iplweb>=0.23.0` → `djangoql-iplweb>=0.25.0`.
- Relock the single package: `uv lock --upgrade-package djangoql-iplweb`
  (keeps the rest of the lock frozen). Verify resolved version is 0.25.0.
- `make assets` (or `grunt build` → `collectstatic`) so the new
  `djangoql/js/{highlight,multiline}.js` and `css/highlight.css` land in
  `STATIC_ROOT` and the manifest is regenerated. No Docker/deploy change (the
  build-stage `.baked` collectstatic picks them up on image rebuild).

### 2. Public view — server side (`src/bpp/views/zapytanie.py`)

Reuse upstream primitives; add a thin error-location bridge ported from the
example project.

- **Error-location helper** (`_error_location(exc, query) -> (line, column,
  mark)`): if the exception carries `.line`/`.column` (lexer/parser errors) →
  use them, `mark='to_end'` (paint the broken tail); else if it carries `.value`
  (schema "unknown field/value" errors) → locate that token in `query` via a
  word-boundary regex (fallback: substring), `mark='token'`. Ported from
  `example_project/library/views.py` `_locate`/`_error_response`. No silent
  swallowing — the catch tuple stays `(DjangoQLError, FieldError,
  ValidationError, ValueError)`.
- **Run path** stays a full-page reload (current architecture). On parse error
  the view adds `error_line`, `error_column`, `error_mark` to the template
  context so the page paints the squiggle on load. The existing `_format_error`
  text callout is kept.
- **New endpoint `bpp:zapytanie_format`** (`zapytanie/format/<model_key>/`,
  POST): `format_query(q)` → `{formatted}`; empty `q` → `{formatted: ""}`; error
  → `400 {error, line, column, mark}`.
- **New endpoint `bpp:zapytanie_explain`** (`zapytanie/explain/<model_key>/`,
  POST): `explain(Model.objects.all(), q, schema=BppZapytanieSchema)` →
  `{tree}`; empty `q` → `{tree: null}`; error → `400 {error,…}`. On-demand for
  any query (distinct from the auto on-zero `explain_empty`).
- **Keep** `explain_empty` for the auto 0-results panel; **enrich**
  `_annotate_breakdown` to read the new `role` field — label the
  `killer_and` node (where the intersection collapses to 0) as the precise
  *winowajca*, and mark `dead_or_branch` nodes; keep the existing leaf message.
- All new endpoints are CBVs gated by `WprowadzanieDanychOrSuperuserMixin` and
  keep CSRF (POST with `X-CSRFToken`; the example's `@csrf_exempt` is a
  demo-only shortcut and is **not** copied).
- `introspect` / `suggestions` endpoints unchanged; during implementation verify
  `SuggestionsAPISerializer` / `SuggestionsAPIView` signatures are unchanged in
  0.25 (they are used as-is).

### 3. Public view — front end

- `src/bpp/templates/bpp/zapytanie.html`:
  - Add static: `djangoql/js/multiline.js`, `djangoql/js/highlight.js`,
    `djangoql/css/highlight.css` (next to the existing `completion.js` /
    `completion.css`).
  - **Delete** the bespoke popup-repositioning IIFE + Tab shim. Keep the
    bpp-specific niceties (localStorage query history, clickable examples /
    result rows) but move the DjangoQL glue out (below).
  - Add a **Format** button and an **Explain counts** button + a results-side
    panel for the on-demand tree.
  - Emit a small `<script type="application/json" id="zapytanie-config">`
    island with the per-model introspect/format/explain/suggestions URLs
    (`{% url %}` reverses) + current model key + CSRF token, so the external JS
    stays template-agnostic.
  - Add the `djangoql-highlight` class (or attach explicitly) to the query
    `<textarea>`; ensure it also carries the `djangoql` class so `multiline.js`
    binds Shift+Enter.
- **New `src/bpp/static/bpp/js/zapytanie.js`** (collectstatic already covers
  `src/bpp/static`), modeled on `example_project/.../demo.js`:
  - Reads the config island.
  - `var overlay = DjangoQLHighlight.attachOverlay(textarea)` (keep handle).
  - `new DjangoQL({ introspections: <introspect URL for current model>,
    selector, syntaxHelp: null, autoResize: false, onSubmit })`; reload
    introspections on model-radio change via `dql.loadIntrospections(url)`.
  - Multiline via the class hook (no explicit `enable()` needed once the
    textarea matches the selector).
  - Format button → POST format endpoint → set textarea value, repaint overlay
    (dispatch `input`); on error → `setErrorAt`/`setErrorFrom`.
  - Explain button → POST explain endpoint → render the tree, coloring each node
    label with `DjangoQLHighlight.renderHtml(node.text)`; on error → squiggle.
  - On page load, if the server passed `error_line/column/mark`, paint the
    squiggle for the just-submitted (Run) query.
- **Popup positioning**: port the example project's caret-anchored popup
  approach (it exists precisely for tall multi-line boxes) instead of BPP's
  bespoke version, and re-verify under BPP's `position:relative; min-height:100vh`
  body. Revisit / trim the current fixed-position `.djangoql-completion` CSS
  hacks accordingly.

### 4. Admin — flags only

- **`BppDjangoQLSearchMixin(DjangoQLSearchMixin)`** (new, likely in
  `src/bpp/admin/helpers/`): sets `djangoql_schema = BppQLSchema` and
  `djangoql_highlight = True`. The 9 `BppQLSchema` admins inherit it and drop
  their local `djangoql_schema = BppQLSchema` line (DRY; centralizes future
  flags). Multiline + auto explain-empty come along automatically.
- The 3 default-schema / `enabled_by_default=False` admins keep their behavior;
  they inherit highlight only when completion is toggled on (leave as-is unless
  a quick win).
- Verify the 3 custom-`change_list_template` admins (wydawnictwo_ciagle,
  wydawnictwo_zwarte, jednostka/grappelli) still render the search box and that
  the overlay works inside grappelli; if grappelli styling fights `highlight.css`,
  add a small sibling fix next to `fix-djangoql-css-for-grappelli.css`.

### 5. Tests (`src/bpp/tests/test_zapytanie.py`, pytest style)

- Format endpoint: valid query → `{formatted}` (idempotent/round-trips);
  invalid → `400` with `error` + `line`/`column`/`mark`.
- Explain endpoint (on-demand): non-empty/non-zero query → a `{tree}` with
  expected `role`s; empty → `{tree: null}`; invalid → `400`.
- Run error path: parse error renders the page with `error_line/column/mark` in
  context.
- Enriched breakdown: `killer_and` node carries the *winowajca* label;
  `dead_or_branch` marked; existing leaf/root behavior preserved.
- Template includes the new static (`highlight.js`, `highlight.css`,
  `multiline.js`) and the config island.
- Admin: `highlight.js`/`highlight.css` present in `BppDjangoQLSearchMixin`
  media (or `djangoql_highlight is True` on the BppQLSchema admins).
- Keep the existing breakdown HTML-assertion tests green (preserve the
  `zapytanie-breakdown-count--zero` markers and partial structure, or update
  deliberately with the enrichment).

### 6. Changelog

One towncrier feature fragment in `src/bpp/newsfragments/`.

## Error handling

- Query parse/validation: catch the specific tuple `(DjangoQLError, FieldError,
  ValidationError, ValueError)`, convert to a user message + error location; no
  bare/silent excepts.
- `explain` / `explain_empty` failures in the view: `logger.exception(...)` and
  degrade to "no breakdown" (matches the existing compliant pattern), never
  swallow silently.
- JS fetch failures: surface the `{error}` text in the existing error callout
  and, when coordinates are present, the overlay squiggle.

## Security / access control

- All new endpoints stay behind `WprowadzanieDanychOrSuperuserMixin` (the public
  view is staff/data-entry-gated, not anonymous).
- CSRF protection retained on the AJAX POST endpoints.
- Suggestions keep flowing through `AutocompleteField` + `_visible_qs`, so hidden
  objects are not leaked.

## Out of scope (YAGNI)

- Format / Explain buttons inside the Django admin (endpoints exist; no UI).
- AJAX-ifying the Run path (stays full-page reload).
- The MongoDB-backed `pbn_api` `PublicationAdmin` schema (left on default).
- Any change to the `<fk>__rel` picker semantics or `BppQLSchema` internals
  beyond what 0.25 compatibility requires.

## Risks

1. The bespoke popup/Tab JS removal + overlay introduction is the largest
   regression surface (caret math under BPP's body layout). Mitigated by porting
   the example project's caret-anchored approach and a manual re-verify pass
   (run-site + browser).
2. Manifest static storage must collect the new `.js`/`.css`/`.map` cleanly;
   `TolerantManifestStaticFilesStorage` tolerates unresolved refs but the new
   files must be present — verify after `make assets`.
3. The 3 custom admin changelist templates + grappelli must keep rendering the
   search box and overlay — verify post-bump.
4. Existing breakdown tests assert on rendered HTML strings — the enrichment
   must preserve those markers or update the assertions deliberately.
