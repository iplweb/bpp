"""Tagi szablonu podstrony autora: składanie sekcji profilu w pasy."""

from django import template
from django.utils.safestring import mark_safe

from bpp.profil_autora import zloz_pasy

register = template.Library()


@register.simple_tag(takes_context=True)
def pasy_profilu(context, sekcje):
    """Wyrenderuj sekcje profilu i złóż je w pasy (``zloz_pasy``).

    Sekcje renderujemy TU, a nie ``{% include %}``-em w pętli, bo parowanie
    musi znać wynik: sekcja tylko-szablonowa bramkuje się sama
    (``{% if %}``) i bywa pusta — a pusta nie może zająć połówki pary, bo
    zostawiłaby dziurę obok sąsiada. Renderujemy w kontekście strony
    (``autor``, ``uczelnia``, ``request``…) z dołożonymi ``dane`` / ``nazwa``
    / ``klucz`` sekcji — tak jak robił to ``{% include … with … %}``.

    Zwraca listę pasów; pas to lista 1–2 sekcji z polem ``html``.
    """
    engine = context.template.engine
    wyrenderowane = []
    for sekcja in sekcje:
        szablon = engine.get_template(sekcja["template"])
        with context.push(
            dane=sekcja["dane"], nazwa=sekcja["nazwa"], klucz=sekcja["klucz"]
        ):
            html = szablon.render(context).strip()
        if html:
            wyrenderowane.append({**sekcja, "html": mark_safe(html)})
    return zloz_pasy(wyrenderowane)
