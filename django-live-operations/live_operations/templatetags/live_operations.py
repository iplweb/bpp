from django import template
from django.utils.html import mark_safe

register = template.Library()


@register.simple_tag
def live_operation(op):
    """Render the live operation container with WS binding attributes.

    Produces:
      <div id="op-<pk>"
           data-liveop-channel="liveop.<pk>"
           data-liveop-token="<signed-token>">
        ... regions ...
      </div>

    Uses render_op_container so both the templatetag and chain_to share
    the same rendering path.
    """
    from live_operations.rendering import render_op_container

    return mark_safe(render_op_container(op))


@register.simple_tag
def render_op_result(op):
    """Render the result fragment for a finished operation (safe HTML).

    Tries op.get_result_template_name() first; falls back to a key=value
    dump of result_context if the template does not exist.
    Returns an empty string for non-finished or failed operations.
    """
    if op.finished_on is None or not op.finished_successfully:
        return mark_safe("")

    render_ctx = dict(op.result_context or {})
    render_ctx.setdefault("operation", op)

    from django.template.loader import render_to_string

    try:
        return mark_safe(render_to_string(op.get_result_template_name(), render_ctx))
    except Exception:
        parts = [
            f"{k}={v}"
            for k, v in render_ctx.items()
            if k != "operation"
        ]
        return mark_safe("<br>".join(parts))


@register.filter
def get_item(dictionary, key):
    """Return ``dictionary[key]`` or empty string when key is absent.

    Used in _stages.html to look up per-stage state by variable key:
      {{ op.stage_states|get_item:stage_name }}
    """
    if not isinstance(dictionary, dict):
        return ""
    return dictionary.get(key, "")
