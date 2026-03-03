import json

from django import template

register = template.Library()


@register.filter(name="pretty_json")
def pretty_json(value):
    """Formatuj wartość jako czytelny JSON string."""
    try:
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return str(value)
