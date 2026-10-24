from urllib.parse import urlsplit

from django import template

register = template.Library()


@register.filter
def host_z_uri(uri):
    """Host (z portem, jeśli podany) z adresu URI — do ekranu zgody OAuth.

    Nazwę klienta ustawia rejestrujący (DCR), więc obok niej pokazujemy host
    z ``redirect_uri``, dokąd faktycznie trafi kod autoryzacyjny. Zwraca
    zwykły ``str`` — autoescape szablonu pozostaje włączony.
    """
    if not uri or not isinstance(uri, str):
        return ""
    try:
        parts = urlsplit(uri)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return ""
    if host and port:
        return f"{host}:{port}"
    return host
