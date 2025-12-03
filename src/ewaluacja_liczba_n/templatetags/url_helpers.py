from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Replace or add URL parameters while preserving existing ones.

    Usage in template:
    {% url_replace sort='name' %} - replaces/adds sort parameter
    {% url_replace sort='name' page=1 %} - replaces/adds multiple parameters

    This prevents duplicate parameters from accumulating in URLs.
    """
    request = context["request"]
    params = request.GET.copy()

    # Update parameters with new values
    for key, value in kwargs.items():
        if value is None or value == "":
            # Remove parameter if value is None or empty
            params.pop(key, None)
        else:
            # Replace or add parameter
            params[key] = value

    # Return the query string (without the ?)
    return params.urlencode()


@register.simple_tag(takes_context=True)
def url_remove(context, *args):
    """
    Remove URL parameters while preserving others.

    Usage in template:
    {% url_remove 'page' %} - removes page parameter
    {% url_remove 'page' 'sort' %} - removes multiple parameters
    """
    request = context["request"]
    params = request.GET.copy()

    # Remove specified parameters
    for key in args:
        params.pop(key, None)

    # Return the query string (without the ?)
    return params.urlencode()


@register.simple_tag(takes_context=True)
def get_sort_url(context, field):
    """
    Generate URL for sorting by a field.
    Toggles between ascending and descending order.

    Usage in template:
    {% get_sort_url 'autor' %} - returns URL for sorting by autor field
    """
    request = context["request"]
    params = request.GET.copy()
    current_sort = params.get("sort", "")

    # Toggle sort direction if clicking on the same field
    if current_sort == field:
        new_sort = f"-{field}"
    elif current_sort == f"-{field}":
        new_sort = field
    else:
        new_sort = field

    params["sort"] = new_sort
    # Reset to first page when changing sort
    params["page"] = "1"

    return "?" + params.urlencode() if params else ""


@register.filter
def get_sort_icon(current_sort, field):
    """
    Return the appropriate sort icon for a field.

    Usage in template:
    {{ current_sort|get_sort_icon:'autor' }}
    """
    if current_sort == field:
        return "↑"  # Ascending
    elif current_sort == f"-{field}":
        return "↓"  # Descending
    return "↕"  # Not sorted


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary using a variable key.

    Usage in template:
    {{ my_dict|get_item:my_key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
