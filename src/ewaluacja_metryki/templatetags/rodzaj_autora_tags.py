from django import template
from django.utils.html import format_html

from ewaluacja_common.models import Rodzaj_Autora

register = template.Library()


@register.filter
def rodzaj_autora_label(skrot):
    """Zwraca HTML label dla danego skrótu rodzaju autora"""
    if skrot == " " or skrot is None:
        return format_html('<span class="label secondary" title="Brak danych">-</span>')

    try:
        rodzaj = Rodzaj_Autora.objects.get(skrot=skrot)
        if skrot == "N":
            css_class = "success"
        elif skrot == "D":
            css_class = "warning"
        elif skrot == "B":
            css_class = "info"
        else:
            css_class = "secondary"

        return format_html(
            '<span class="label {}" title="{}">{}</span>',
            css_class,
            rodzaj.nazwa,
            skrot,
        )
    except Rodzaj_Autora.DoesNotExist:
        return format_html(
            '<span class="label secondary" title="{}">{}</span>', skrot, skrot
        )


@register.filter
def rodzaj_autora_nazwa(skrot):
    """Zwraca nazwę dla danego skrótu rodzaju autora"""
    if skrot == " " or skrot is None:
        return "Brak danych"

    try:
        rodzaj = Rodzaj_Autora.objects.get(skrot=skrot)
        return rodzaj.nazwa
    except Rodzaj_Autora.DoesNotExist:
        return skrot
