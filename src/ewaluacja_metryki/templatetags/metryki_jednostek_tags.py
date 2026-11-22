"""Tagi szablonu zestawienia „Metryki jednostki” (FD#617)."""

from django import template

from .. import metryki_jednostek_svg as svg

register = template.Library()


@register.filter
def pierscien_wypelnienia(wiersz):
    return svg.pierscien_wypelnienia(wiersz)


@register.filter
def pierscien_punktow(wiersz):
    return svg.pierscien_punktow(wiersz)


@register.filter
def wykres_babelkowy(grupa, dopelniacz="jednostki"):
    return svg.wykres_babelkowy(grupa, dopelniacz=dopelniacz)


@register.filter
def pasek_struktury(grupa):
    return svg.pasek_struktury(grupa)


@register.simple_tag
def pierscien_jednostki(procent, tekst, status=None):
    kolor = svg.KOLOR_STATUSU.get(status, svg.NIEBIESKI)
    return svg.pierscien_jednostki(procent, tekst, kolor)


@register.simple_tag
def legenda_struktury(grupa):
    return list(zip(grupa.struktura, svg.KOLORY_PRZEDZIALOW, strict=True))
