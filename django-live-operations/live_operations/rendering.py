"""
Shared rendering helpers for live_operations.

render_op_container: renders the live_operation container fragment for a
given operation, optionally annotated with an hx-swap-oob attribute for
chain_to OOB swaps.  Used by:
  - live_operations templatetag
  - WebProgress.chain_to  (passes oob_target to trigger OOB container swap)
"""
from __future__ import annotations

from typing import Any, Optional


def render_op_container(op: Any, oob_target: Optional[str] = None) -> str:
    """Return rendered HTML for the live_operation container.

    *op*         — LiveOperation instance.
    *oob_target* — if given, the rendered element will carry
                   ``hx-swap-oob="outerHTML:#<oob_target>"`` so that the
                   client-side OOB handler replaces the old container
                   in-place (used by chain_to).
    """
    from django.template.loader import render_to_string

    return render_to_string(
        "live_operations/_live_operation.html",
        {"op": op, "oob_target": oob_target},
    )
