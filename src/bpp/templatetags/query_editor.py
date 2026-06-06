from django import template

from bpp.views.zapytanie import user_can_use_query_editor

register = template.Library()


@register.filter(name="can_use_query_editor")
def can_use_query_editor(user):
    """True, gdy user moze korzystac z edytora zapytan DjangoQL."""
    if user is None:
        return False
    return user_can_use_query_editor(user)
