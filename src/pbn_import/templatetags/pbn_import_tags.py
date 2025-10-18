"""Template tags for PBN import"""

import html
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_json(value):
    """Format JSON data for display"""
    if not value:
        return ""

    try:
        # If it's a string, try to parse it as JSON
        if isinstance(value, str):
            data = json.loads(value)
        else:
            data = value

        # Pretty print with indentation
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        # Escape HTML and wrap in pre tag
        return mark_safe(f'<pre class="json-display">{html.escape(formatted)}</pre>')
    except (json.JSONDecodeError, TypeError):
        # If not JSON, just return the value wrapped in pre
        return mark_safe(f'<pre class="json-display">{html.escape(str(value))}</pre>')


@register.filter
def is_json(value):
    """Check if a string value is valid JSON"""
    if not value or not isinstance(value, str):
        return False

    try:
        json.loads(value)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


@register.filter
def is_error_log(log):
    """Check if a log entry is an error or critical level"""
    return log.level in ["error", "critical", "warning"]


@register.filter
def truncate_message(message, length=100):
    """Truncate a message to specified length"""
    if not message:
        return ""

    if len(message) <= length:
        return message

    return message[:length] + "..."
