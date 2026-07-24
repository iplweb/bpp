"""Favicon podążający za hostem (multi-tenant), bez patchowania biblioteki.

``django-favicon-plus-reloaded`` renderuje favicon tagiem ``place_favicon``,
który pyta ``Favicon.on_site`` — a ``on_site`` to ``CurrentSiteManager``.
Jego ``get_queryset()`` filtruje ``.filter(site__id=settings.SITE_ID)``,
czyli po LITERALNYM ``settings.SITE_ID``. ``SiteResolutionMiddleware`` nie
podmienia ``SITE_ID`` per request (ustawia tylko ``request.site`` /
``request._uczelnia``), więc oryginalny tag serwuje ten sam favicon pod
każdą domeną — favicon w ogóle nie podąża za hostem.

Ten tag omija ograniczenie, NIE dotykając biblioteki: pyta zwykły menedżer
``Favicon.objects`` (nie ``on_site``) i filtruje po ``request.site``, które
``SiteResolutionMiddleware`` rozstrzyga z Host → Site. ``Favicon.site`` to
zwykły FK w modelu biblioteki, a ``as_html()`` jest host-niezależny (renderuje
tylko ``<link>`` po URL-ach obrazów), więc korzystamy z nich wprost.
"""

from django import template
from django.utils.safestring import mark_safe
from favicon.models import Favicon

register = template.Library()


@register.simple_tag(takes_context=True)
def place_favicon(context):
    """Wstaw ``<link>`` faviconu dla Site rozstrzygniętego z hosta.

    Fallback: gdy nie ma ``request`` albo ``request.site`` (np. wołanie spoza
    cyklu żądania, świeża instalacja bez Site), degradujemy do zachowania
    biblioteki (``Favicon.on_site`` po ``settings.SITE_ID``) — single-host
    działa jak wcześniej.
    """
    request = context.get("request")
    site = getattr(request, "site", None) if request is not None else None

    if site is None:
        fav = Favicon.on_site.filter(isFavicon=True).first()
    else:
        fav = Favicon.objects.filter(site=site, isFavicon=True).first()

    if not fav:
        return mark_safe("<!-- no favicon -->")

    return mark_safe(fav.as_html())
