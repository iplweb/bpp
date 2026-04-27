# Tailwind component partials

These are Django template partials that author the same visual contract
as the Foundation components they replace, but using Tailwind utilities
+ Alpine.js. New templates should `{% include "components/<name>.html" %}`
instead of writing Foundation `class="callout primary"` markup.

During the Foundation -> Tailwind migration both styles work — partials
use Tailwind classes, the legacy `class="callout"` etc. continues to
work via the compat layer in `static/tailwind/_components.css`.

See `docs/TAILWIND_MIGRATION.md` for the full convention.
