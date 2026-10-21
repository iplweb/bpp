from django import template
from django.contrib.auth.models import Group

from bpp.permissions import moze_wprowadzac_dane

register = template.Library()


@register.filter(name="has_group")
def has_group(user, group_name):
    group = Group.objects.get(name=group_name)
    return True if group in user.cached_groups else False


@register.filter(name="moze_wprowadzac_dane")
def moze_wprowadzac_dane_filter(user):
    """True, gdy ``user`` ma uprawnienia redaktorskie (superuser lub grupa
    „wprowadzanie danych") — ta sama bramka, co w
    ``WprowadzanieDanychRequiredMixin``. Do ukrywania linków do widoków,
    które innym użytkownikom zwróciłyby 403."""
    if user is None:
        return False
    return moze_wprowadzac_dane(user)
