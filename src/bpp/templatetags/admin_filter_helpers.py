"""
Template tags for admin filter panel helpers.
"""

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag
def get_filter_choices(spec, cl):
    """
    Get choices for a filter spec.

    Args:
        spec: The filter specification object
        cl: The ChangeList object

    Returns:
        List of choice dictionaries with 'selected', 'query_string', and 'display' keys
    """
    return list(spec.choices(cl))


@register.simple_tag
def get_filter_choices_without_selected(spec, cl):
    """
    Get choices for a filter spec, excluding the selected one.

    Args:
        spec: The filter specification object
        cl: The ChangeList object

    Returns:
        List of choice dictionaries excluding the currently selected option
    """
    choices = list(spec.choices(cl))

    # Always show first choice (typically "All") and any non-selected choices
    result = []
    for i, choice in enumerate(choices):
        if i == 0 or not choice.get("selected"):
            result.append(choice)
        elif choice.get("selected"):
            # Also include selected choice if it's a default value
            display = choice.get("display", "").lower()
            if display in [
                "all",
                "wszystkie",
                "wszyscy",
                "wszystko",
                "-",
                "---",
                "",
                "none",
            ]:
                result.append(choice)

    return result


@register.simple_tag
def get_selected_filter_value(spec, cl):
    """
    Get the selected value for a filter spec (excluding "All").

    Args:
        spec: The filter specification object
        cl: The ChangeList object

    Returns:
        String with selected filter display value, or empty string if none selected
    """
    choices = list(spec.choices(cl))

    # First choice is typically "All" - if it's selected, return empty
    if choices and choices[0].get("selected"):
        return ""

    for choice in choices:
        if choice.get("selected"):
            # Skip default/all values (in various languages and forms)
            display = choice.get("display", "")
            if display.lower() in [
                "all",
                "wszystkie",
                "wszyscy",
                "wszystko",
                "-",
                "---",
                "",
                "none",
                "empty",
                "dowolny",
                "dowolna",
                "dowolne",
                "jakikolwiek",
                "jakiekolwiek",
                "jakakolwiek",
            ]:
                return ""
            return display
    return ""


@register.simple_tag
def get_filter_count_url(choice, cl):
    """
    Generuje URL dla HTMX count request dla danego filtru.

    Args:
        choice: Dictionary z filter choice (zawiera 'query_string')
        cl: The ChangeList object

    Returns:
        String z pełnym URL do endpointu filter-count wraz z query stringiem
    """
    # Zbuduj nazwę URL bazując na app_label i model_name
    url_name = (
        f"admin:{cl.model._meta.app_label}_{cl.model._meta.model_name}_filter_count"
    )

    try:
        # Pobierz bazowy URL
        base_url = reverse(url_name)

        # Dodaj query string z choice
        query_string = choice.get("query_string", "")
        if query_string:
            # query_string może zaczynać się od '?' - usuń to
            if query_string.startswith("?"):
                query_string = query_string[1:]
            return f"{base_url}?{query_string}"
        else:
            return base_url
    except Exception:
        # W przypadku błędu zwróć pusty string
        # (HTMX nie wywoła requestu dla pustego URL)
        return ""


@register.simple_tag
def get_selected_filter_count_url(spec, cl):
    """
    Get the filter count URL for the currently selected filter value.

    Args:
        spec: The filter specification object
        cl: The ChangeList object

    Returns:
        URL string for HTMX request to get count, or empty string if no selection
    """
    choices = list(spec.choices(cl))
    for choice in choices:
        if choice.get("selected") and choice.get("display") not in [
            "All",
            "Wszystkie",
            "Wszyscy",
        ]:
            # Found the selected choice, return its count URL
            return get_filter_count_url(choice, cl)
    return ""
