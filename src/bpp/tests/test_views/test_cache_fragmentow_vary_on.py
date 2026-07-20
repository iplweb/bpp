"""Każdy fragment-cache w szablonach musi mieć ``vary_on`` — albo alibi.

DLACZEGO to musi istnieć: BPP jest wielo-uczelniane (jeden proces, wiele
domen; ``SiteResolutionMiddleware`` rozstrzyga Host → Site → Uczelnia).
Fragment cache'owany pod GLOBALNYM kluczem serwuje treść uczelni A pod
domeną uczelni B. Tak zdarzyło się ze snippetem Google Analytics
(``{% cache 3600 google %}`` w ``base.html``) — ruch jednej uczelni
raportował się do konta Google innej.

Test wymusza świadomą decyzję: albo fragment ma ``vary_on``, albo trafia
na listę wyjątków RAZEM z uzasadnieniem, dlaczego jest host-niezależny.
"""

import re
from pathlib import Path

KATALOG_ZRODEL = Path(__file__).resolve().parents[3]

#: Fragmenty cache'owane pod globalnym kluczem, dla których udowodniono,
#: że ich treść NIE zależy od hosta/uczelni/użytkownika.
#:
#: * ``favicon`` (``django_bpp/templates/bare.html``) — renderuje
#:   ``{% place_favicon %}`` z pakietu ``django-favicon-plus``, który pyta
#:   ``Favicon.on_site`` (``CurrentSiteManager``). Ten manager filtruje po
#:   ``Site.objects.get_current()``, a ta — wywołana bez ``request`` —
#:   czyta STAŁE ``settings.SITE_ID``. ``SiteResolutionMiddleware`` nie
#:   podmienia ``SITE_ID`` per request (ustawia tylko ``request.site`` i
#:   ``request._uczelnia``), więc wynik jest identyczny pod każdą domeną i
#:   globalny klucz jest poprawny. (Osobna sprawa, że favicon przez to w
#:   ogóle nie podąża za hostem — to ograniczenie pakietu, nie cache'a.)
DOZWOLONE_BEZ_VARY_ON = {"favicon"}

TAG_CACHE = re.compile(r"{%\s*cache\s+(?P<argumenty>[^%]*?)\s*%}")


def _szablony():
    for katalog in ("bpp", "django_bpp"):
        yield from (KATALOG_ZRODEL / katalog).rglob("*.html")


def test_kazdy_fragment_cache_ma_vary_on_albo_alibi():
    bez_vary_on = []

    for szablon in _szablony():
        for dopasowanie in TAG_CACHE.finditer(szablon.read_text(encoding="utf-8")):
            argumenty = dopasowanie.group("argumenty").split()
            # argumenty[0] = czas życia, argumenty[1] = nazwa fragmentu,
            # reszta (jeśli jest) = vary_on.
            if len(argumenty) < 2:
                continue
            nazwa = argumenty[1]
            if len(argumenty) > 2 or nazwa in DOZWOLONE_BEZ_VARY_ON:
                continue
            bez_vary_on.append(f"{szablon.relative_to(KATALOG_ZRODEL)}: {nazwa}")

    assert not bez_vary_on, (
        "fragment-cache pod globalnym kluczem — w instalacji wielo-uczelnianej "
        "treść jednej uczelni wycieknie na domenę innej. Dodaj vary_on albo "
        "dopisz do DOZWOLONE_BEZ_VARY_ON z uzasadnieniem: " + ", ".join(bez_vary_on)
    )
