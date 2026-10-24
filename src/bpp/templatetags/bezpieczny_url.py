from django import template

from bpp.util.bezpieczny_url import czy_bezpieczny_link

register = template.Library()


@register.filter(name="bezpieczny_url")
def bezpieczny_url(value):
    """Zwróć adres, jeżeli ma schemat http/https; w przeciwnym razie ""."""
    if value and czy_bezpieczny_link(value):
        return value
    return ""
