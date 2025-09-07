from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag
def build_query_string(request, **kwargs):
    """
    Build a query string preserving existing parameters but updating/removing specified ones.

    Usage in template:
    {% build_query_string request sort='-nazwisko' %}
    {% build_query_string request page=2 %}
    {% build_query_string request sort='-nazwisko' page=None %}  # Remove page param
    """
    # Create a mutable copy of the QueryDict
    if hasattr(request, "GET"):
        params = request.GET.copy()
    else:
        params = QueryDict("", mutable=True)

    for key, value in kwargs.items():
        if value is None:
            # Remove the parameter if value is None
            params.pop(key, None)
        else:
            # Update or add the parameter
            params[key] = value

    # Always remove 'page' when changing sort
    if "sort" in kwargs and "page" not in kwargs:
        params.pop("page", None)

    query_string = params.urlencode()
    return f"?{query_string}" if query_string else ""


@register.simple_tag
def update_query_param(request, param_name, param_value):
    """
    Update a single query parameter, preserving all others except 'page'.
    Removes 'page' parameter when updating 'sort' to reset pagination.
    """
    # Create a mutable copy of the QueryDict
    if hasattr(request, "GET"):
        params = request.GET.copy()
    else:
        params = QueryDict("", mutable=True)

    if param_value is None:
        params.pop(param_name, None)
    else:
        params[param_name] = param_value

    # Remove page when changing sort
    if param_name == "sort":
        params.pop("page", None)

    query_string = params.urlencode()
    return f"?{query_string}" if query_string else ""


@register.simple_tag
def preserve_filters(request, **kwargs):
    """
    Preserve filter parameters but update specified ones.
    Useful for pagination links that need to preserve filters but change page.
    """
    # Create a mutable copy of the QueryDict
    if hasattr(request, "GET"):
        params = request.GET.copy()
    else:
        params = QueryDict("", mutable=True)

    # Update specified parameters
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value

    query_string = params.urlencode()
    return f"?{query_string}" if query_string else ""
