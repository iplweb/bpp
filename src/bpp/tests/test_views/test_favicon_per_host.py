"""Favicon podąża za hostem (multi-tenant) — bez patchowania biblioteki.

Sedno: ``bpp.templatetags.favicon_bpp.place_favicon`` pyta ``Favicon.objects``
po ``request.site`` (rozstrzygniętym z Host → Site przez
``SiteResolutionMiddleware``), a fragment ``{% cache 3600 favicon
request.get_host %}`` ma ``vary_on`` na hoście.

``test_cache_*`` MUSZĄ biec na REALNYM backendzie (LocMem), nie DummyCache —
inaczej ``cache.get`` zawsze zwraca ``None`` i test „izolacji" przeszedłby z
niewłaściwego powodu (bo nic nie byłoby zapamiętane). Wzorzec z
``test_cache_publiczny.py``.
"""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from PIL import Image

from favicon.models import Favicon

from fixtures.conftest_multisite import make_request_for_site

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-favicon-per-host",
    }
}


@pytest.fixture(autouse=True)
def _zezwol_na_hosty_testowe(settings):
    """Domeny fixture'ów (``uczelnia1.localhost``) muszą przejść ``get_host``."""
    settings.ALLOWED_HOSTS = ["*"]


@pytest.fixture
def cache_locmem(settings):
    """Podmień domyślny (Dummy) cache na LocMem i wyczyść wokół testu."""
    from django.core.cache import cache

    poprzednie = settings.CACHES
    settings.CACHES = {**poprzednie, **LOCMEM}
    cache.clear()
    yield cache
    cache.clear()
    settings.CACHES = poprzednie


def _png_bytes(kolor):
    buf = BytesIO()
    Image.new("RGB", (32, 32), kolor).save(buf, format="PNG")
    return buf.getvalue()


def _utworz_favicon(site, tytul, kolor):
    """Favicon dla danego Site z rozpoznawalnym po tytule URL-em obrazu.

    ``FaviconImg.as_html`` renderuje ``href`` po nazwie pliku
    (``slugify(title)-<size>s.png``), więc różne tytuły → różne ``<link>``.

    Tworzymy NORMALNĄ ścieżką (``Favicon.objects.create`` → ``save()``), tak
    jak robi to admin biblioteki. Dzięki patchowi ``_patch_favicon_save_per_site``
    (``bpp.apps``) reset ``isFavicon`` jest per ``self.site``, więc zapis
    favicona jednego tenanta NIE gasi już favicona innego — nie trzeba żadnego
    ``.update()`` omijającego ``save()`` (który wcześniej maskował buga).
    """
    return Favicon.objects.create(
        title=tytul,
        site=site,
        faviconImage=SimpleUploadedFile(
            f"{tytul}.png", _png_bytes(kolor), content_type="image/png"
        ),
    )


@pytest.fixture
def favicon_uczelnia1(site1):
    return _utworz_favicon(site1, "UczelniaJeden", "red")


@pytest.fixture
def favicon_uczelnia2(site2):
    return _utworz_favicon(site2, "UczelniaDwa", "blue")


@pytest.fixture
def favicony_obu(favicon_uczelnia1, favicon_uczelnia2):
    """Oba favicony utworzone normalną ścieżką ``save()``.

    Po naprawie zapis drugiego favicona nie gasi flagi pierwszego, więc obie
    pozostają aktywne bez re-afirmacji.
    """
    return favicon_uczelnia1, favicon_uczelnia2


FRAGMENT = Template(
    "{% load cache favicon_bpp %}"
    "{% cache 3600 favicon request.get_host %}"
    "{% place_favicon %}"
    "{% endcache %}"
)


def _renderuj(request):
    return FRAGMENT.render(Context({"request": request}))


# ---------------------------------------------------------------------------
# TAG — favicon podąża za hostem (bez cache'a)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tag_zwraca_favicon_wlasciwego_hosta(site1, site2, favicony_obu):
    """Pod domeną uczelni 1 — favicon uczelni 1, nie uczelni 2."""
    from bpp.templatetags.favicon_bpp import place_favicon

    html1 = place_favicon({"request": make_request_for_site(site1)})
    html2 = place_favicon({"request": make_request_for_site(site2)})

    assert "uczelniajeden" in html1
    assert "uczelniadwa" not in html1, (
        "Pod domeną uczelni 1 wyrenderował się favicon uczelni 2 — favicon "
        "nie podąża za hostem."
    )
    assert "uczelniadwa" in html2
    assert "uczelniajeden" not in html2


@pytest.mark.django_db
def test_zapis_favicona_tenanta_b_nie_gasi_favicona_tenanta_a(site1, site2):
    """Ścieżka ZAPISU: create favicona site2 NIE gasi ``isFavicon`` site1.

    Regresja Critical z code review: ``Favicon.save()`` biblioteki woła
    ``on_site.exclude(pk).update(isFavicon=False)`` po ``settings.SITE_ID``.
    ``site1`` ma ``pk=1`` == ``SITE_ID``, więc BEZ patcha utworzenie favicona
    ``site2`` gasi flagę favicona ``site1`` (tenant spod SITE_ID traci
    favicon). Tworzymy oba NORMALNĄ ścieżką ``create()``/``save()`` (jak
    admin) i sprawdzamy, że oba zostają aktywne.

    Dowód, że test łapie buga: po tymczasowym cofnięciu patcha (przywróceniu
    ``Favicon.on_site.exclude(...).update(...)`` w ``save``) ten test FAILUJE
    na asercji ``f1.isFavicon``.
    """
    f1 = _utworz_favicon(site1, "UczelniaJeden", "red")
    assert f1.isFavicon is True

    # Zapis favicona DRUGIEGO tenanta — nie może ruszyć favicona pierwszego.
    _utworz_favicon(site2, "UczelniaDwa", "blue")

    f1.refresh_from_db()
    assert f1.isFavicon is True, (
        "CLOBBERING: zapis favicona site2 zgasił isFavicon favicona site1 "
        "(spod SITE_ID) — ścieżka save() gasi cudzego tenanta."
    )


@pytest.mark.django_db
def test_zapis_favicona_gasi_poprzedni_favicon_TEGO_SAMEGO_site(site1):
    """Semantyka „jeden aktywny favicon per site” MUSI zostać zachowana.

    Drugi favicon TEGO SAMEGO site'u ma zgasić pierwszy (per-site reset),
    inaczej patch złamałby oryginalne zachowanie biblioteki.
    """
    f1 = _utworz_favicon(site1, "PierwszyU1", "red")
    f2 = _utworz_favicon(site1, "DrugiU1", "green")

    f1.refresh_from_db()
    assert f1.isFavicon is False, (
        "Drugi favicon tego samego site'u nie zgasił pierwszego — złamana "
        "semantyka „jeden aktywny favicon per site”."
    )
    assert f2.isFavicon is True


@pytest.mark.django_db
def test_tag_bez_site_degraduje_do_on_site(site1, favicon_uczelnia1):
    """Brak ``request`` (wołanie spoza cyklu żądania) nie wysypuje tagu."""
    from bpp.templatetags.favicon_bpp import place_favicon

    # Nie asertujemy treści (zależy od SITE_ID) — tylko że tag nie rzuca i
    # zwraca string.
    assert isinstance(place_favicon({}), str)


# ---------------------------------------------------------------------------
# CACHE FRAGMENTU — izolacja per host na REALNYM backendzie
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cache_fragmentu_nie_przenosi_faviconu_miedzy_hostami(
    cache_locmem, site1, site2, favicony_obu
):
    """Rozgrzej fragment pod hostem 1, odczytaj pod hostem 2 — różne favicony.

    Bez ``vary_on`` na ``request.get_host`` drugi render dostałby
    zapamiętany favicon uczelni 1 (fragment-cache NIE ma hosta w kluczu
    inaczej niż cache_page). Test na LocMem realnie zapamiętuje — pod
    DummyCache przeszedłby fałszywie.
    """
    html1 = _renderuj(make_request_for_site(site1))
    assert "uczelniajeden" in html1

    html2 = _renderuj(make_request_for_site(site2))
    assert "uczelniadwa" in html2, (
        "WYCIEK MIĘDZY UCZELNIAMI: pod domeną uczelni 2 pojawił się favicon "
        "uczelni 1 z cache'a fragmentu bez hosta w kluczu."
    )
    assert "uczelniajeden" not in html2


@pytest.mark.django_db
def test_cache_fragmentu_trafia_dla_tego_samego_hosta(
    cache_locmem, site1, favicon_uczelnia1
):
    """Ten sam host dwa razy — drugi render to trafienie (identyczny wynik)."""
    pierwszy = _renderuj(make_request_for_site(site1))
    drugi = _renderuj(make_request_for_site(site1))

    assert pierwszy == drugi
    assert "uczelniajeden" in pierwszy
