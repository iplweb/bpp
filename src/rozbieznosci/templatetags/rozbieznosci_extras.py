from django import template

register = template.Library()


@register.filter
def attr(obj, name):
    """Return getattr(obj, name, '') — used in templates for dynamic field access."""
    return getattr(obj, name, "")
