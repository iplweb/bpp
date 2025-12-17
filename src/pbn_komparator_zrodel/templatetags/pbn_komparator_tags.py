from django import template

register = template.Library()


@register.simple_tag
def dyscyplina_display(codes_str, wyswietlaj_nazwy, cache):
    """
    Display discipline codes or names with proper spacing.

    Args:
        codes_str: Comma-separated string of discipline codes (e.g., "1.1,2.21,5.3")
        wyswietlaj_nazwy: Boolean - if True, show names instead of codes
        cache: Dictionary mapping codes to names (e.g., {"1.1": "matematyka", ...})

    Returns:
        Formatted string with proper spacing and optionally names
    """
    if not codes_str:
        return "-"

    codes = [c.strip() for c in codes_str.split(",")]

    if wyswietlaj_nazwy and cache:
        return ", ".join(cache.get(c, c) for c in codes)

    return ", ".join(codes)


@register.filter
def dyscyplina_count(codes_str):
    """Count number of disciplines in comma-separated string."""
    if not codes_str:
        return 0
    return len([c for c in codes_str.split(",") if c.strip()])
