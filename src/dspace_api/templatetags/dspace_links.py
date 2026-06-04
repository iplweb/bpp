"""Tagi szablonów do linkowania rekordów w repozytorium DSpace."""

from django import template

from dspace_api.links import public_links_for_rec

register = template.Library()


@register.simple_tag
def dspace_repo_links(rec):
    """Zwróć listę ``(Uczelnia, url)`` do rekordu w repozytoriach DSpace.

    Użycie: ``{% dspace_repo_links praca as repo_links %}`` a potem iteracja.
    Pusta lista → rekord nie został wysłany / brak handle."""
    if rec is None or getattr(rec, "pk", None) is None:
        return []
    return public_links_for_rec(rec)
