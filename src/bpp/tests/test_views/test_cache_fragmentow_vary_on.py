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
#: Aktualnie PUSTE. Favicon (``django_bpp/templates/bare.html``) był tu
#: kiedyś z alibi, że favicon i tak nie podąża za hostem (bug
#: ``django-favicon-plus-reloaded``: ``Favicon.on_site`` filtruje po
#: literalnym ``settings.SITE_ID``). Ten bug został naprawiony —
#: ``bpp.templatetags.favicon_bpp.place_favicon`` pyta ``Favicon.objects``
#: po ``request.site`` (Host → Site), więc favicon podąża za hostem, a
#: fragment ``{% cache 3600 favicon request.get_host %}`` dostał
#: ``vary_on`` na hoście. Alibi przestało obowiązywać, wpis zniknął.
DOZWOLONE_BEZ_VARY_ON: set[str] = set()

TAG_CACHE = re.compile(r"{%\s*cache\s+(?P<argumenty>[^%]*?)\s*%}")

#: Katalogi, które nie zawierają szablonów Django renderowanych przez BPP:
#: artefakty builda/instalacji oraz pliki statyczne (serwowane dosłownie,
#: nigdy nie przechodzą przez silnik szablonów).
POMIJANE_KATALOGI = frozenset(
    (
        "node_modules",
        "staticroot",
        "static",
        "site-packages",
        "__pycache__",
        ".venv",
        ".tox",
        "htmlcov",
    )
)


def _szablony():
    """Wszystkie szablony pod ``src/`` — CAŁE drzewo, nie tylko ``bpp``.

    Zasięg celowo obejmuje każdą aplikację (``admin_dashboard``,
    ``rozbieznosci_dyscyplin``, ``ewaluacja_optymalizacja``, …): tag
    dodany poza ``bpp`` jest dokładnie tym przypadkiem, dla którego ten
    strażnik istnieje.
    """
    for sciezka in KATALOG_ZRODEL.rglob("*.html"):
        # Tylko część WZGLĘDNA — gdyby któryś katalog NAD repo nazywał się
        # np. "static", filtr po pełnej ścieżce wyciszyłby cały test.
        wzgledna = sciezka.relative_to(KATALOG_ZRODEL)
        if POMIJANE_KATALOGI.isdisjoint(wzgledna.parts):
            yield sciezka


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
