from urllib.parse import urlencode

import pytest
from cacheops import invalidate_obj
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls.base import reverse

from bpp.const import DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY, NAJWIEKSZY_REKORD
from bpp.models import Uczelnia
from bpp.models.fields import OpcjaWyswietlaniaField
from bpp.tests import browse_praca_url, normalize_html
from raport_slotow import const
from raport_slotow.views import SESSION_KEY

# Disable cache for all tests in this file
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_cache_for_tests(settings):
    """
    Disable caching for all tests in this module.
    This ensures that changes to Uczelnia object are immediately visible.
    """
    # Disable Django cache. The `constance_cache` entry must remain defined
    # because django-constance's DatabaseBackend does `caches[<name>]` on
    # first access to `constance.config` and would raise
    # InvalidCacheBackendError if the key is missing.
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
        "constance_cache": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
    }
    # Disable cacheops
    settings.CACHEOPS_ENABLED = False


def clear_uczelnia_cache(uczelnia):
    """
    Helper function to clear all caches related to Uczelnia object.
    This is needed in tests where we modify Uczelnia attributes and expect
    immediate visibility of changes.

    Clears:
    1. Cacheops cache for get_uczelnia_context_data function
    2. Django cache for uczelnia context processor
    3. All cacheops caches for Uczelnia model
    """
    # Invalidate cacheops cache for the uczelnia object
    invalidate_obj(uczelnia)

    # Clear Django cache used by context processor
    cache.delete(b"bpp_uczelnia")

    # Clear all caches (including @cached decorated functions)
    cache.clear()


@pytest.mark.parametrize(
    "attr,s",
    [
        ("pokazuj_punktacje_wewnetrzna", "Punktacja wewnętrzna"),
        ("pokazuj_index_copernicus", "Index Copernicus"),
    ],
)
def test_uczelnia_praca_pokazuj(uczelnia, wydawnictwo_ciagle, attr, s, client):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

    setattr(uczelnia, attr, True)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert s in res.rendered_content

    setattr(uczelnia, attr, False)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert s not in res.rendered_content


@pytest.mark.parametrize(
    "attr,s",
    [
        ("pokazuj_status_korekty", "Status"),
        ("pokazuj_praca_recenzowana", "Praca recenzowana"),
    ],
)
def test_uczelnia_praca_pokazuj_pozostale(
    uczelnia, wydawnictwo_ciagle, client, admin_client, attr, s
):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s not in res.rendered_content


# Menu raportów (nowe_raporty) jest teraz data-driven (DefinicjaRaportu),
# niezależne od Uczelnia.pokazuj_raport_* (pola usunięte) - jego widoczność
# pokrywają testy w src/nowe_raporty/tests/. Tu zostaje tylko ranking autorów,
# który dalej jest sterowany flagą na Uczelni.
lista_stron_raportow = [
    ("pokazuj_ranking_autorow", b'ranking-autorow/wybierz/"><i'),
]


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_zawsze(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s in res.content

    res = admin_client.get(url, follow=True)
    assert s in res.content


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_zalogowani(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s not in res.content

    res = admin_client.get(url, follow=True)
    assert s in res.content


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_nigdy(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url, follow=True)
    assert s not in res.content

    res = admin_client.get(url, follow=True)
    assert s not in res.content


@pytest.mark.django_db
def test_pokazuj_tabele_slotow_na_stronie_rekordu(
    uczelnia,
    admin_client,
    client,
    praca_z_dyscyplina,
):
    url = browse_praca_url(praca_z_dyscyplina)

    S = "Punkty i sloty autorów"

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S not in res.rendered_content


@pytest.mark.parametrize(
    "poszukiwany_ciag,atrybut_uczelni",
    [
        ("raport slotów - autor", "pokazuj_raport_slotow_autor"),
        ("raport slotów - uczelnia", "pokazuj_raport_slotow_uczelnia"),
        ("raport slotów - zerowy", "pokazuj_raport_slotow_zerowy"),
    ],
)
@pytest.mark.django_db
def test_pokazuj_raport_slotow_menu_na_glownej(
    uczelnia, admin_client, client, poszukiwany_ciag, atrybut_uczelni, db
):
    url = reverse("bpp:browse_uczelnia", args=(uczelnia.slug,))
    S = poszukiwany_ciag

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S not in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)


@pytest.mark.parametrize(
    "nazwa_url,atrybut_uczelni,params",
    [
        ("raport_slotow:index", "pokazuj_raport_slotow_autor", {}),
        (
            "raport_slotow:raport-slotow-zerowy-parametry",
            "pokazuj_raport_slotow_zerowy",
            {},
        ),
        (
            "raport_slotow:raport-slotow-zerowy-wyniki",
            "pokazuj_raport_slotow_zerowy",
            {
                "od_roku": 2020,
                "do_roku": 2020,
                "min_pk": 0,
                "rodzaj_raportu": "SL",
                "_export": "html",
            },
        ),
        (
            "raport_slotow:raport",
            "pokazuj_raport_slotow_autor",
            {},
        ),
        (
            "raport_slotow:lista-raport-slotow-uczelnia",
            "pokazuj_raport_slotow_uczelnia",
            {},
        ),
        (
            "raport_slotow:lista-raport-slotow-uczelnia",
            "pokazuj_raport_slotow_uczelnia",
            {"od_roku": 2000, "do_roku": 2000, "maksymalny_slot": 1, "_export": "html"},
        ),
    ],
)
@pytest.mark.django_db
def test_pokazuj_raport_slotow_czy_mozna_kliknac(
    uczelnia, admin_client, client, autor, nazwa_url, atrybut_uczelni, params
):
    url = reverse(nazwa_url)
    if nazwa_url == "raport_slotow:raport":
        dane_raportu = {
            "obiekt": autor.pk,
            "od_roku": 2016,
            "do_roku": 2017,
            "dzialanie": const.DZIALANIE_SLOT,
            "minimalny_pk": 0,
            "slot": 19,
            "_export": "html",
        }

        for c in admin_client, client:
            s = c.session
            s.update({SESSION_KEY: dane_raportu})
            s.save()

    if params:
        url += "?" + urlencode(params)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert res.status_code == 302
    res = admin_client.get(url)
    assert res.status_code == 200

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert res.status_code == 404
    res = admin_client.get(url)
    assert res.status_code == 404

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    res = client.get(url)
    assert res.status_code == 302
    res = admin_client.get(url)
    assert res.status_code == 200

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    if atrybut_uczelni == "pokazuj_raport_slotow_uczelnia":
        # dla opcji "pokazuj raport slotów uczelnia" login jest zawsze wymagany
        pass
    else:
        res = client.get(url)
        assert res.status_code == 200
        res = admin_client.get(url)
        assert res.status_code == 200


def test_uczelnia_obca_jednostka(uczelnia, jednostka, obca_jednostka):
    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()

    uczelnia.obca_jednostka = jednostka
    with pytest.raises(ValidationError):
        uczelnia.save()


def test_uczelnia_ukryte_statusy(uczelnia, przed_korekta, po_korekcie):
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    uczelnia.ukryj_status_korekty_set.create(status_korekty=po_korekcie)

    assert przed_korekta.pk in uczelnia.ukryte_statusy("sloty")
    assert po_korekcie.pk in uczelnia.ukryte_statusy("sloty")


def test_uczelnia_do_roku_default(uczelnia, wydawnictwo_zwarte):
    wydawnictwo_zwarte.rok = 3000
    wydawnictwo_zwarte.save()

    uczelnia.metoda_do_roku_formularze = DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY
    uczelnia.save()

    assert Uczelnia.objects.do_roku_default() != 3000

    uczelnia.metoda_do_roku_formularze = NAJWIEKSZY_REKORD
    uczelnia.save()

    assert Uczelnia.objects.do_roku_default() == 3000


# Realny backend dla testu inwalidacji: domyślny DummyCache z autouse
# ``disable_cache_for_tests`` nic nie zapisuje, więc na nim inwalidacji NIE
# da się zaobserwować (każdy ``get`` to miss). Podmieniamy na LocMem (wzorzec
# z ``test_cache_publiczny.py``), by przejść PEŁNĄ ścieżkę zapis→odczyt→
# inwalidacja context-procesora ``uczelnia`` (górny pasek, strona główna).
LOCMEM_UCZELNIA = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-invalidacja-uczelnia",
    }
}


def test_zapis_uczelni_inwaliduje_cache_strony_glownej(uczelnia, settings, mocker):
    """Zapis Uczelni FAKTYCZNIE unieważnia cache kontekstu strony głównej.

    Poprzednia wersja mockowała ``cache.delete`` — dowodziła tylko, że sygnał
    WOŁA ``delete(klucz)``, a nie że context-procesor czyta ten SAM klucz ani
    że po zapisie serwuje świeżą wartość (tautologia względem prawdziwego
    backendu). Tu, na realnym ``LocMemCache``, sprawdzamy skutek: pierwsze
    żądanie zapisuje kontekst, zapis Uczelni go usuwa, kolejne żądanie dostaje
    nową nazwę zamiast zapamiętanej starej.

    Zakres: weryfikujemy realnie warstwę Django-cache (klucz
    ``bpp_uczelnia_<site_pk>``). Druga warstwa — ``get_uczelnia_context_data``
    (``@cached`` cacheops) — jest w testach globalnie wyłączona (INSTALLED_APPS
    bez ``cacheops`` + ``CACHEOPS_ENABLED=False``, patrz ``settings/test.py``),
    a włączanie cacheopsa per-test to landmine (globalny monkey-patch, cross-
    worker leak w Redisie pod xdist). Jej podpięcie pilnujemy osobno: ``spy``
    potwierdza, że sygnał woła ``.invalidate()``.
    """
    from django.core.cache import cache
    from django.test import RequestFactory

    from bpp.context_processors.uczelnia import _cache_key_for_request
    from bpp.context_processors.uczelnia import uczelnia as uczelnia_ctx
    from bpp.views.browse import get_uczelnia_context_data

    # Override autouse ``disable_cache_for_tests`` (DummyCache) na realny LocMem.
    settings.CACHES = {**settings.CACHES, **LOCMEM_UCZELNIA}
    cache.clear()

    # Spy (nie mock): przepuszcza prawdziwe wywołanie, tylko je liczy — pilnuje
    # podpięcia inwalidacji warstwy cacheopsa (w testach będącej no-opem).
    spy_invalidate = mocker.spy(get_uczelnia_context_data, "invalidate")

    site = uczelnia.site

    def swiezy_request():
        # Symuluje osobne żądanie HTTP: ``request.site`` ustawia w produkcji
        # ``SiteResolutionMiddleware`` — tu ustawiamy je ręcznie tak samo.
        r = RequestFactory().get("/", HTTP_HOST=site.domain)
        r.site = site
        return r

    klucz = _cache_key_for_request(swiezy_request())

    # 1. Pierwsze żądanie zapisuje kontekst strony głównej do cache.
    assert cache.get(klucz) is None
    ctx1 = uczelnia_ctx(swiezy_request())
    assert ctx1["uczelnia"].nazwa == "Testowa uczelnia"
    assert cache.get(klucz) is not None, "pierwsze żądanie nie zapisało cache"

    # 2. Warunek kontrolny (reguła #8): zmiana z POMINIĘCIEM sygnału
    #    (``update`` nie wysyła post_save) NIE unieważnia — kolejne żądanie
    #    dostaje STARĄ wartość z cache. Dowodzi, że cache naprawdę trzyma
    #    migawkę; inaczej asercja z p. 3 przechodziłaby, bo cache nie działa.
    Uczelnia.objects.filter(pk=uczelnia.pk).update(nazwa="Nazwa z pominietym sygnalem")
    ctx_stale = uczelnia_ctx(swiezy_request())
    assert ctx_stale["uczelnia"].nazwa == "Testowa uczelnia", (
        "cache nie zwrócił zapamiętanej wartości — LocMem nie działa, więc "
        "test inwalidacji niczego by nie dowodził"
    )

    # 3. Zapis przez ``save()`` → sygnał ``invalidate_uczelnia_caches`` →
    #    ``cache.delete(klucz)``. Kolejne żądanie MUSI dostać świeżą nazwę.
    uczelnia.nazwa = "Nazwa po zapisie"
    uczelnia.save()

    assert cache.get(klucz) is None, (
        "zapis Uczelni nie usunął klucza cache context-procesora — "
        "inwalidacja NIE działa"
    )
    spy_invalidate.assert_called_once_with()

    ctx2 = uczelnia_ctx(swiezy_request())
    assert ctx2["uczelnia"].nazwa == "Nazwa po zapisie", (
        "po zapisie Uczelni strona główna nadal serwuje starą nazwę z cache "
        "— inwalidacja context-procesora nie działa"
    )
