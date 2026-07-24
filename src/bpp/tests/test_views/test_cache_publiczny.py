"""Testy cache'a HTTP publicznych stron przeglądania (anonim).

Najważniejszy jest tu ``test_izolacja_multi_host_*`` — MUSI padać, gdyby
ktoś usunął hosta z klucza cache'a (``bpp.views.cache_publiczny._klucz``).
"""

import pytest
from django.core.cache import cache
from django.urls import reverse
from model_bakery import baker

from bpp.views.cache_publiczny import (
    _klucz,
    _mozna_cachowac_odpowiedz,
    cache_publiczny,
    uniewaznij_cache_publiczny,
)

from fixtures.conftest_multisite import make_request_for_site

# W ``settings/test.py`` CACHES["default"] to DummyCache — nic nie
# zapamiętuje, więc bez podmiany na LocMem te testy nie mierzyłyby niczego.
LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache-publiczny",
    }
}


@pytest.fixture
def cache_locmem(settings):
    """Podmień domyślny cache na LocMem i wyczyść go przed/po teście."""
    poprzednie = settings.CACHES
    settings.CACHES = {**poprzednie, **LOCMEM}
    cache.clear()
    yield cache
    cache.clear()
    settings.CACHES = poprzednie


@pytest.fixture(autouse=True)
def _zezwol_na_hosty_testowe(settings):
    settings.ALLOWED_HOSTS = ["*"]


@pytest.fixture
def czysta_kolejka_on_commit(db):
    """Wyczyść unieważnienia zaplanowane przez fixture'y.

    ``uniewaznij_cache_publiczny`` planuje pracę przez
    ``transaction.on_commit`` i pomija kolejne zgłoszenia, gdy jedno już
    czeka w tej transakcji. Pod ``django_db`` transakcja testu NIGDY nie
    commituje, więc unieważnienia zaplanowane przez fixture'y (zapis
    ``Uczelnia``, ``Jednostka``…) zostają w kolejce i wyciszyłyby
    wszystko, co test chce zmierzyć. Czyścimy kolejkę, żeby test
    startował jak świeża transakcja.

    Zamawiaj ten fixture JAKO OSTATNI, po fixture'ach tworzących modele.
    """
    from django.db import transaction

    transaction.get_connection().run_on_commit.clear()
    yield


def uniewaznij_i_zatwierdz(django_capture_on_commit_callbacks):
    """Unieważnij cache tak, jak zrobiłby to prawdziwy ``COMMIT``.

    Prawdziwy commit wykonuje callbacki I opróżnia ``run_on_commit``.
    Testowy harness ich nie usuwa, więc bez wyczyszczenia kolejki dedup
    z ``uniewaznij_cache_publiczny`` uznałby kolejne unieważnienie za już
    zaplanowane i je pominął. Czyścimy po obu stronach, żeby każde
    wywołanie startowało z granicy transakcji.
    """
    from django.db import transaction

    polaczenie = transaction.get_connection()
    polaczenie.run_on_commit.clear()
    with django_capture_on_commit_callbacks(execute=True):
        uniewaznij_cache_publiczny()
    polaczenie.run_on_commit.clear()


# ---------------------------------------------------------------------------
# IZOLACJA MULTI-HOST — sedno tego modułu
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_izolacja_multi_host_klucz_zawiera_hosta(
    cache_locmem, site1, site2, uczelnia1, uczelnia2
):
    """Ten sam URL pod dwiema domenami MUSI dać dwa różne klucze cache'a.

    ``cache_locmem`` jest tu WARUNKIEM SENSOWNOŚCI testu, nie ozdobą: pod
    domyślnym ``DummyCache`` ``cache.get`` zawsze zwraca ``None``, więc
    ``_generacja()`` losuje nowy identyfikator przy każdym wywołaniu i dwa
    klucze różniłyby się nawet wtedy, gdyby host w ogóle do nich nie
    wchodził. Test przechodziłby wtedy z niewłaściwego powodu.
    """
    r1 = make_request_for_site(site1, path="/bpp/autorzy/")
    r2 = make_request_for_site(site2, path="/bpp/autorzy/")

    assert r1.get_full_path() == r2.get_full_path()
    # Warunek kontrolny: bez zmiany hosta klucz musi być stabilny.
    assert _klucz(r1) == _klucz(r1)
    assert _klucz(r1) != _klucz(r2), (
        "Klucz cache'a nie rozróżnia domen — cache zaserwuje treść jednej "
        "uczelni pod domeną drugiej. Patrz docstring bpp.views.cache_publiczny."
    )


@pytest.mark.django_db
def test_izolacja_multi_host_rozne_tresci_pod_roznymi_domenami(
    client,
    cache_locmem,
    site1,
    site2,
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
):
    """Domena A nie może dostać cache'a wygenerowanego dla domeny B.

    To jest test przeciw wyciekowi danych MIĘDZY INSTYTUCJAMI. Jeżeli
    ktoś usunie ``request.get_host()`` z ``_klucz``, drugie żądanie
    dostanie zapamiętaną stronę uczelni 1 i asercje niżej padną.
    """
    url = reverse("bpp:browse_jednostki")

    # Rozgrzewamy cache pod domeną uczelni 1.
    odp1 = client.get(url, HTTP_HOST=site1.domain)
    assert odp1.status_code == 200
    assert jednostka_uczelnia1.nazwa in odp1.content.decode()

    # A teraz TEN SAM URL pod domeną uczelni 2.
    odp2 = client.get(url, HTTP_HOST=site2.domain)
    assert odp2.status_code == 200
    tresc2 = odp2.content.decode()

    assert jednostka_uczelnia2.nazwa in tresc2
    assert jednostka_uczelnia1.nazwa not in tresc2, (
        "WYCIEK MIĘDZY UCZELNIAMI: pod domeną uczelni 2 pojawiła się "
        "jednostka uczelni 1 — najpewniej z cache'a bez hosta w kluczu."
    )

    # Drugie żądanie na domenę 1 nadal ma dane uczelni 1 (a nie 2).
    odp1b = client.get(url, HTTP_HOST=site1.domain)
    tresc1b = odp1b.content.decode()
    assert jednostka_uczelnia1.nazwa in tresc1b
    assert jednostka_uczelnia2.nazwa not in tresc1b


# ---------------------------------------------------------------------------
# ANONIM vs ZALOGOWANY
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cache_dziala_dla_anonima(client, cache_locmem, site1, uczelnia1):
    """Drugie żądanie anonima jest obsłużone z cache'a (HIT)."""
    url = reverse("bpp:browse_lata")

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"

    druga = client.get(url, HTTP_HOST=site1.domain)
    assert druga.status_code == 200
    assert druga["X-BPP-Cache"] == "HIT"
    assert druga.content == pierwsza.content


@pytest.mark.django_db
def test_cache_dla_anonima_scina_zapytania_do_bazy(
    client, cache_locmem, site1, uczelnia1, jednostka_uczelnia1
):
    """Trafienie w cache eliminuje zapytania widoku o treść strony.

    Zera nie da się tu wymagać: ``SiteResolutionMiddleware`` rozstrzyga
    ``Host`` → ``Site`` → ``Uczelnia`` ZANIM dekorator w ogóle zobaczy
    żądanie (i musi to robić — to od tego zależy klucz cache'a). Zostaje
    więc stała, mała podłoga zapytań middleware'owych. Mierzymy to, co
    cache faktycznie obiecuje: że znika praca WIDOKU.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse("bpp:browse_jednostki")

    with CaptureQueriesContext(connection) as zimne:
        assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "MISS"

    with CaptureQueriesContext(connection) as cieple:
        assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"

    assert len(cieple) < len(zimne), (
        f"Cache nie ściął ani jednego zapytania "
        f"(zimne={len(zimne)}, ciepłe={len(cieple)})."
    )
    # Podłoga middleware'owa: rozstrzygnięcie Site/Uczelni. Gdyby urosła,
    # znaczy że coś poza cache'em zaczęło odpytywać bazę na każdej stronie.
    assert len(cieple) <= 5, [q["sql"] for q in cieple.captured_queries]


@pytest.mark.django_db
def test_zalogowany_nie_czyta_cache_anonima(
    client, cache_locmem, site1, uczelnia1, superuser_multisite
):
    """Zalogowany dostaje stronę wyrenderowaną dla siebie, nie kopię anonima."""
    url = reverse("bpp:browse_lata")

    anonim = client.get(url, HTTP_HOST=site1.domain)
    assert anonim["X-BPP-Cache"] == "MISS"

    client.force_login(superuser_multisite)
    zalogowany = client.get(url, HTTP_HOST=site1.domain)

    assert zalogowany.status_code == 200
    assert not zalogowany.has_header("X-BPP-Cache"), (
        "Zalogowany przeszedł przez warstwę cache'a — a miał ją ominąć."
    )


@pytest.mark.django_db
def test_anonim_nie_czyta_cache_zalogowanego(
    client, cache_locmem, site1, uczelnia1, superuser_multisite
):
    """Odpowiedź dla zalogowanego nie może trafić do cache'a anonimów."""
    url = reverse("bpp:browse_lata")

    client.force_login(superuser_multisite)
    client.get(url, HTTP_HOST=site1.domain)

    client.logout()
    anonim = client.get(url, HTTP_HOST=site1.domain)

    assert anonim["X-BPP-Cache"] == "MISS", (
        "Anonim dostał HIT-a, choć cache rozgrzewał tylko zalogowany — "
        "znaczy, że zapisaliśmy odpowiedź zalogowanego."
    )


# ---------------------------------------------------------------------------
# INWALIDACJA
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_zapis_publikacji_uniewaznia_cache(
    client,
    cache_locmem,
    site1,
    uczelnia1,
    jednostka_uczelnia1,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Po zapisie w adminie publiczna strona odświeża się natychmiast.

    Unieważnienie leci przez ``transaction.on_commit`` (patrz
    ``uniewaznij_cache_publiczny``), a ``django_db`` trzyma test w
    transakcji, która nigdy nie commituje — stąd jawne wykonanie
    callbacków.
    """
    url = reverse("bpp:browse_jednostki")

    client.get(url, HTTP_HOST=site1.domain)
    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"

    with django_capture_on_commit_callbacks(execute=True):
        jednostka_uczelnia1.nazwa = "Jednostka Po Zmianie"
        jednostka_uczelnia1.save()

    po_zapisie = client.get(url, HTTP_HOST=site1.domain)
    assert po_zapisie["X-BPP-Cache"] == "MISS"
    assert "Jednostka Po Zmianie" in po_zapisie.content.decode()


@pytest.mark.django_db
def test_bump_generacji_zawsze_zmienia_klucz(
    cache_locmem,
    site1,
    uczelnia1,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Kolejne unieważnienia zawsze dają nowy klucz (nigdy nie wracają)."""
    request = make_request_for_site(site1, path="/bpp/lata/")

    widziane = {_klucz(request)}
    for _ in range(5):
        uniewaznij_i_zatwierdz(django_capture_on_commit_callbacks)
        widziane.add(_klucz(request))

    assert len(widziane) == 6


@pytest.mark.django_db
def test_utrata_klucza_generacji_nie_wskrzesza_starych_wpisow(
    cache_locmem,
    site1,
    uczelnia1,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Eksmisja klucza generacji nie może przywrócić WCZEŚNIEJSZEJ wartości.

    Regresja po recenzji. Poprzednia wersja seedowała licznik zegarem i
    inkrementowała go przy każdym zapisie: masowy import wyprzedzał zegar,
    a eksmisja klucza przez ``maxmemory`` Redisa cofała generację poniżej
    ostatnio używanej — wskrzeszając wpisy z całego okna TTL. Poprzedni
    test przechodził PUSTO, bo sprawdzał wartość natychmiast po skasowaniu,
    gdy licznik nie zdążył jeszcze wyprzedzić zegara.

    Tu odtwarzamy właściwy scenariusz: dużo unieważnień, potem eksmisja.
    """
    from bpp.views.cache_publiczny import _KLUCZ_GENERACJI, _generacja

    widziane = {_generacja()}

    for _ in range(50):
        uniewaznij_i_zatwierdz(django_capture_on_commit_callbacks)
        widziane.add(_generacja())

    # Redis z maxmemory eksmituje klucz generacji.
    cache.delete(_KLUCZ_GENERACJI)
    po_eksmisji = _generacja()

    assert len(widziane) == 51, "unieważnienia powtórzyły generację"
    assert po_eksmisji not in widziane, (
        "Generacja po eksmisji powtórzyła wcześniejszą wartość — wpisy "
        "zapamiętane pod nią wracają do obiegu."
    )


@pytest.mark.django_db
def test_jedna_transakcja_to_jedno_uniewaznienie(
    cache_locmem,
    site1,
    uczelnia1,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Importer w bloku ``atomic`` nie robi round-tripu na każdy wiersz."""
    with django_capture_on_commit_callbacks() as callbacki:
        for _ in range(20):
            uniewaznij_cache_publiczny()

    assert len(callbacki) == 1, (
        f"20 zapisów zaplanowało {len(callbacki)} unieważnień — dedup "
        "per transakcja nie działa."
    )


@pytest.mark.django_db
def test_wycofana_transakcja_nie_blokuje_kolejnych_uniewaznien(
    cache_locmem,
    site1,
    uczelnia1,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Po rollbacku mechanizm dedup nie może zostać zakleszczony.

    Gdyby dedup opierał się na własnej, „lepkiej" fladze na połączeniu,
    wycofana transakcja zostawiłaby ją ustawioną i wyciszyła WSZYSTKIE
    kolejne unieważnienia. Dlatego skanujemy ``run_on_commit``, które
    Django samo czyści przy rollbacku.
    """
    from django.db import transaction

    class _Wycofaj(Exception):
        pass

    try:
        with transaction.atomic():
            uniewaznij_cache_publiczny()
            raise _Wycofaj()
    except _Wycofaj:
        pass

    with django_capture_on_commit_callbacks() as callbacki:
        uniewaznij_cache_publiczny()

    assert len(callbacki) == 1, (
        "Unieważnienie po wycofanej transakcji nie zostało zaplanowane — "
        "mechanizm dedup zakleszczył się."
    )


# ---------------------------------------------------------------------------
# ZGODA NA CIASTECZKA (cookielaw) — regresja po recenzji
# ---------------------------------------------------------------------------
#
# ``base.html`` renderuje baner cookielaw i snippet Google Analytics na
# podstawie ciasteczka ``cookielaw_accepted``. Wszystkie trzy warianty są
# anonimowe, więc bramkowanie na ``is_anonymous`` nic nie dawało: strona
# rozgrzana przez osobę, która wyraziła zgodę, niosła znacznik GA do
# WSZYSTKICH, także do tych, którzy kliknęli „nie zgadzam się".
# Naprawa: stan zgody wchodzi do klucza cache'a (``_stan_zgody``).


@pytest.mark.django_db
def test_klucz_rozroznia_stany_zgody(cache_locmem, site1, uczelnia1):
    """Trzy stany zgody muszą dać trzy różne klucze."""
    klucze = set()
    for ciasteczko in (None, "1", "0"):
        request = make_request_for_site(site1, path="/bpp/lata/")
        if ciasteczko is not None:
            request.COOKIES["cookielaw_accepted"] = ciasteczko
        klucze.add(_klucz(request))

    assert len(klucze) == 3, (
        "Klucz nie rozróżnia stanu zgody — cache przeniesie zgodę jednego "
        "odwiedzającego na wszystkich pozostałych."
    )


@pytest.mark.django_db
def test_cache_nie_przenosi_zgody_miedzy_odwiedzajacymi(
    client, cache_locmem, site1, uczelnia1, settings
):
    """Scenariusz z recenzji: rozgrzej zgodą, odbierz odmową.

    To jest test przeciw obejściu zgody na śledzenie (RODO/ePrivacy),
    nie przeciw kosmetyce banera.
    """
    settings.GOOGLE_ANALYTICS_PROPERTY_ID = "testowy-identyfikator-ga"
    url = reverse("bpp:browse_lata")

    client.cookies.clear()
    client.cookies["cookielaw_accepted"] = "1"
    akceptujacy = client.get(url, HTTP_HOST=site1.domain)
    assert akceptujacy["X-BPP-Cache"] == "MISS"

    client.cookies.clear()
    client.cookies["cookielaw_accepted"] = "0"
    odmawiajacy = client.get(url, HTTP_HOST=site1.domain)

    assert odmawiajacy["X-BPP-Cache"] == "MISS", (
        "Odmawiający dostał stronę z cache'a rozgrzanego przez osobę, "
        "która wyraziła zgodę."
    )
    assert "googletagmanager.com" not in odmawiajacy.content.decode(), (
        "OBEJŚCIE ZGODY: strona dla odmawiającego niesie znacznik Google "
        "Analytics."
    )


@pytest.mark.django_db
def test_ten_sam_stan_zgody_wciaz_trafia_w_cache(
    client, cache_locmem, site1, uczelnia1
):
    """Rozdzielenie po zgodzie nie może zabić trafialności w obrębie kubełka."""
    url = reverse("bpp:browse_lata")

    client.cookies.clear()
    client.cookies["cookielaw_accepted"] = "1"
    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "MISS"
    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_robot_indeksujacy_dzieli_jeden_kubelek(cache_locmem, site1, uczelnia1):
    """Ruch, który ten cache ma odciążyć, nie jest rozdrabniany.

    Roboty nie wykonują JavaScriptu, więc nigdy nie ustawiają ciasteczka
    zgody — wszystkie trafiają do tego samego kubełka.
    """
    pierwszy = make_request_for_site(site1, path="/bpp/lata/")
    drugi = make_request_for_site(site1, path="/bpp/lata/")

    assert _klucz(pierwszy) == _klucz(drugi)


@pytest.mark.django_db
def test_smieciowe_ciasteczko_nie_tlumi_banera_zgody(
    client, cache_locmem, site1, uczelnia1
):
    """Spreparowanym ciasteczkiem nie da się ukryć banera nowym osobom.

    Regresja po drugiej recenzji. Wartość nieznana renderuje się jak
    ``"0"`` (bez banera, bez GA), ale wpadała do kubełka „brak" — razem
    z ``None``. Rozgrzanie cache'a śmieciem podawało więc świeżemu
    odwiedzającemu stronę BEZ banera zgody, czyli tłumiło komunikat
    prawny na czas TTL.
    """
    url = reverse("bpp:browse_lata")

    client.cookies.clear()
    client.cookies["cookielaw_accepted"] = "spreparowana-wartosc"
    rozgrzewajacy = client.get(url, HTTP_HOST=site1.domain)
    assert rozgrzewajacy["X-BPP-Cache"] == "MISS"
    assert "CookielawBanner" not in rozgrzewajacy.content.decode()

    # Świeży odwiedzający — bez żadnego ciasteczka.
    client.cookies.clear()
    swiezy = client.get(url, HTTP_HOST=site1.domain)

    assert swiezy["X-BPP-Cache"] == "MISS", (
        "Świeży odwiedzający dostał stronę z cache'a rozgrzanego "
        "śmieciowym ciasteczkiem."
    )
    assert "CookielawBanner" in swiezy.content.decode(), (
        "TŁUMIENIE KOMUNIKATU PRAWNEGO: świeży odwiedzający nie dostał "
        "banera zgody na ciasteczka."
    )


@pytest.mark.django_db
def test_nieznana_wartosc_ciasteczka_jest_rownowazna_odmowie(
    cache_locmem, site1, uczelnia1
):
    """Kubełek ma odpowiadać RENDEROWANIU, a nie surowej wartości.

    ``base.html`` używa tylko ``cookielaw.notset`` i ``cookielaw.accepted``
    (``rejected`` nigdzie), więc wartość nieznana renderuje się dokładnie
    tak jak ``"0"`` — i musi dzielić z nią kubełek.
    """
    from bpp.views.cache_publiczny import _stan_zgody

    def stan(wartosc):
        request = make_request_for_site(site1, path="/bpp/lata/")
        if wartosc is not None:
            request.COOKIES["cookielaw_accepted"] = wartosc
        return _stan_zgody(request)

    assert stan("smiec") == stan("0")
    assert stan("smiec") != stan(None)
    assert stan(None) == "brak"
    assert stan("1") == "zgoda"


@pytest.mark.django_db
def test_dowolna_wartosc_ciasteczka_nie_zalewa_cache(cache_locmem, site1, uczelnia1):
    """Wartość ciasteczka jest sterowana przez klienta — musi być znormalizowana.

    Bez normalizacji atakujący generuje nieograniczoną liczbę wariantów
    tej samej strony i zapycha pamięć Redisa.
    """
    klucze = set()
    for smiec in ("1", "0", "", "xxx", "1 ", "TRUE", "../../etc/passwd", "9" * 500):
        request = make_request_for_site(site1, path="/bpp/lata/")
        request.COOKIES["cookielaw_accepted"] = smiec
        klucze.add(_klucz(request))

    assert len(klucze) <= 3, (
        f"Ciasteczko zgody tworzy {len(klucze)} wariantów klucza — "
        "brak normalizacji, cache da się zalać."
    )


# ---------------------------------------------------------------------------
# BEZPIECZNIKI
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_nie_cachujemy_odpowiedzi_z_tokenem_csrf():
    """Współdzielony token CSRF to dziura — taka treść nie może wejść do cache'a.

    Bezpiecznik działa jako defense-in-depth: strony browse (autor,
    jednostka, zrodlo, uczelnia) NIE renderują już ``{% csrf_token %}``
    (formularz celuje w ``@csrf_exempt`` ``BuildSearch``), więc wchodzą do
    cache'a. Gdyby jednak ktoś dodał do cache'owanego szablonu formularz
    stanowego widoku z tokenem, ten bezpiecznik nie pozwoli go współdzielić.
    """
    from django.http import HttpResponse

    z_tokenem = HttpResponse(
        b'<form><input name="csrfmiddlewaretoken" value="abc"></form>'
    )
    assert not _mozna_cachowac_odpowiedz(z_tokenem)

    bez_tokenu = HttpResponse(b"<p>zwykla tresc</p>")
    assert _mozna_cachowac_odpowiedz(bez_tokenu)


@pytest.mark.django_db
def test_bezpiecznik_lapie_takze_gole_csrf_token():
    """Regresja po recenzji: ``{{ csrf_token }}`` bez pola formularza.

    Bezpiecznik szukał wyłącznie ``csrfmiddlewaretoken``, więc token
    wstawiony przez gołe ``{{ csrf_token }}`` — idiomatyczne dla
    ``<meta name="csrf-token">``, globala JS albo atrybutu ``data-`` —
    przechodził i zostałby współdzielony. Fallback na ``Set-Cookie`` też
    tu nie działa: ``TemplateResponse`` renderuje się (i callback zapisu
    odpala) wewnątrz ``_get_response``, ZANIM ``CsrfViewMiddleware``
    ustawi ciasteczko ``csrftoken`` — więc ``response.cookies`` jest w tym
    momencie puste.
    """
    from django.http import HttpResponse

    # Wartość celowo pozbawiona cech sekretu (małe litery, myślniki, niska
    # entropia): skanery sekretów flagują wysokoentropijne literały
    # przypisane do zmiennej o nazwie ``token``. Dla tego testu wartość i
    # tak nie ma znaczenia — sprawdzamy wyłącznie, czy bezpiecznik
    # zauważa ciąg „csrf" w treści.
    udawana_wartosc = "wartosc-z-testu"
    warianty = {
        "meta": f'<meta name="csrf-token" content="{udawana_wartosc}">',
        "js": f'<script>window.CSRF="{udawana_wartosc}";</script>',
        "data-": f'<div data-csrf="{udawana_wartosc}"></div>',
    }

    for nazwa, tresc in warianty.items():
        assert not _mozna_cachowac_odpowiedz(HttpResponse(tresc.encode())), nazwa


@pytest.mark.django_db
def test_powracajacy_odwiedzajacy_dostaje_304(client, cache_locmem, site1, uczelnia1):
    """ETag pozwala odpowiedzieć 304 zamiast przesyłać całe ciało."""
    url = reverse("bpp:browse_lata")

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    etag = pierwsza["ETag"]
    assert etag

    trzecia = client.get(url, HTTP_HOST=site1.domain, HTTP_IF_NONE_MATCH=etag)
    assert trzecia.status_code == 304
    assert trzecia.content == b""


@pytest.mark.django_db
def test_nie_cachujemy_odpowiedzi_ustawiajacej_ciasteczko():
    """Zamrożony ``Set-Cookie`` byłby współdzielony przez wszystkich."""
    from django.http import HttpResponse

    odpowiedz = HttpResponse(b"tresc")
    odpowiedz.set_cookie("sessionid", "sekret")
    assert not _mozna_cachowac_odpowiedz(odpowiedz)


@pytest.mark.django_db
def test_nie_cachujemy_bledow():
    from django.http import HttpResponse

    assert not _mozna_cachowac_odpowiedz(HttpResponse(b"nie ma", status=404))


@pytest.mark.django_db
def test_odpowiedz_z_cache_ma_cache_control_private(
    client, cache_locmem, site1, uczelnia1
):
    """nginx/CDN nie mogą zrobić drugiej, niebramkowanej kopii."""
    url = reverse("bpp:browse_lata")

    for _ in range(2):
        odp = client.get(url, HTTP_HOST=site1.domain)
        assert "private" in odp["Cache-Control"]
        assert "must-revalidate" in odp["Cache-Control"]
        assert "max-age=0" in odp["Cache-Control"]


@pytest.mark.django_db
def test_post_nie_jest_cachowany(cache_locmem, site1, uczelnia1):
    """Dekorator przepuszcza metody inne niż GET/HEAD bez dotykania cache'a."""
    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpResponse
    from django.test import RequestFactory

    wywolania = []

    @cache_publiczny()
    def widok(request):
        wywolania.append(1)
        return HttpResponse(b"ok")

    factory = RequestFactory()
    for _ in range(2):
        request = factory.post("/cokolwiek/", HTTP_HOST=site1.domain)
        request.user = AnonymousUser()
        widok(request)

    assert len(wywolania) == 2


@pytest.mark.django_db
def test_strona_autora_jest_cachowana(
    client, cache_locmem, site1, uczelnia1, autor_uczelnia1
):
    """Strona autora (wysoki ruch) trafia teraz do cache'a.

    Formularz „szukaj publikacji" celuje w ``@csrf_exempt`` ``BuildSearch``,
    więc szablon nie renderuje już ``{% csrf_token %}`` i bezpiecznik
    ``_ZAWIERA_CSRF`` go przepuszcza. Wcześniej ten sam URL był świadomie
    wykluczony z cache'a — patrz historia tego testu.
    """
    url = reverse("bpp:browse_autor", args=(autor_uczelnia1.pk,))

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"
    assert b"csrf" not in pierwsza.content.lower(), (
        "Strona autora nadal zawiera 'csrf' w treści — bezpiecznik ją "
        "odrzuci i cache nie zadziała."
    )

    druga = client.get(url, HTTP_HOST=site1.domain)
    assert druga["X-BPP-Cache"] == "HIT", (
        "Strona autora nie trafiła do cache'a — najpewniej token CSRF "
        "przetrwał w treści."
    )
    assert druga.content == pierwsza.content


@pytest.mark.django_db
def test_strona_jednostki_jest_cachowana(
    client, cache_locmem, site1, uczelnia1, jednostka_uczelnia1
):
    """Strona jednostki wchodzi do cache'a po usunięciu tokenu CSRF."""
    url = reverse("bpp:browse_jednostka", args=(jednostka_uczelnia1.slug,))

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"
    assert b"csrf" not in pierwsza.content.lower()

    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_strona_zrodla_jest_cachowana(client, cache_locmem, site1, uczelnia1, zrodlo):
    """Strona źródła wchodzi do cache'a po usunięciu tokenu CSRF."""
    url = reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"
    assert b"csrf" not in pierwsza.content.lower()

    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_strona_uczelni_jest_cachowana(client, cache_locmem, site1, uczelnia1):
    """Strona uczelni wchodzi do cache'a po usunięciu tokenu CSRF."""
    url = reverse("bpp:browse_uczelnia", args=(uczelnia1.slug,))

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"
    assert b"csrf" not in pierwsza.content.lower()

    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_izolacja_multi_host_strona_autora(
    client,
    cache_locmem,
    site1,
    site2,
    uczelnia1,
    uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
):
    """Cache strony autora respektuje separację hostów (multi-tenant).

    Autor uczelni 1 pod domeną 1 i autor uczelni 2 pod domeną 2 to różne
    ścieżki, ale dla pewności rozgrzewamy oba i sprawdzamy, że treść z
    jednej domeny nie wycieka pod drugą — klucz cache'a zawiera hosta.
    """
    url1 = reverse("bpp:browse_autor", args=(autor_uczelnia1.pk,))
    url2 = reverse("bpp:browse_autor", args=(autor_uczelnia2.pk,))

    odp1 = client.get(url1, HTTP_HOST=site1.domain)
    assert odp1.status_code == 200
    assert autor_uczelnia1.nazwisko in odp1.content.decode()

    # Ten sam URL autora 1, ale pod OBCĄ domeną (uczelnia 2) — nie może
    # dostać zapamiętanej treści spod domeny 1.
    odp_obca = client.get(url1, HTTP_HOST=site2.domain)
    assert odp_obca["X-BPP-Cache"] == "MISS", (
        "WYCIEK MIĘDZY UCZELNIAMI: strona autora rozgrzana pod domeną 1 "
        "została zaserwowana pod domeną 2 — klucz cache'a nie zawiera hosta."
    )

    # Drugie żądanie pod domeną 1 nadal HIT (własny wpis nietknięty).
    assert client.get(url1, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_build_search_dziala_bez_tokenu_csrf(
    client, site1, uczelnia1, autor_uczelnia1
):
    """POST na ``browse_build_search`` bez tokenu CSRF nie zwraca 403.

    ``@csrf_exempt`` na ``BuildSearch`` sprawia, że formularz bez
    ``{% csrf_token %}`` przechodzi. Wynik to przekierowanie (302) na
    ``multiseek:index`` po zapisaniu wyszukiwania do sesji.
    """
    from django.test import Client

    # ``enforce_csrf_checks=True`` — bez wyłączenia byłby fałszywie zielony,
    # bo domyślny klient testowy w ogóle nie sprawdza CSRF.
    surowy_klient = Client(enforce_csrf_checks=True)
    url = reverse("bpp:browse_build_search")

    odp = surowy_klient.post(
        url,
        data={"autor": str(autor_uczelnia1.pk), "suggested-title": "Test"},
        HTTP_HOST=site1.domain,
    )

    assert odp.status_code != 403, (
        "POST bez tokenu CSRF dostał 403 — @csrf_exempt na BuildSearch nie "
        "zadziałał."
    )
    assert odp.status_code == 302


@pytest.mark.django_db
def test_rok_jest_cachowany(client, cache_locmem, site1, uczelnia1):
    """Strona roku (deterministyczna dla anonima) korzysta z cache'a."""
    url = reverse("bpp:browse_rok", args=("2020",))

    pierwsza = client.get(url, HTTP_HOST=site1.domain)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"
    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"


@pytest.mark.django_db
def test_strona_rekordu_naprawde_sie_cachuje(
    client, cache_locmem, site1, uczelnia1, wydawnictwo_ciagle
):
    """Strona rekordu to najcenniejszy cel cache'a — sprawdź, że działa.

    Bezpiecznik CSRF dopasowuje teraz samo „csrf", bez rozróżniania
    wielkości liter. Gdyby ten ciąg pojawił się gdziekolwiek w
    wyrenderowanym ``browse/praca.html`` (albo w którymkolwiek z jego
    include'ów), cache po cichu przestałby zapisywać, a strona nadal
    wyglądałaby normalnie. Ten test łapie taką cichą regresję.
    """
    from django.contrib.contenttypes.models import ContentType

    # Wzorzec jak w istniejących testach (``test_autorzy_dla_opisu_skrocony``):
    # ``browse_praca`` przekierowuje na URL ze slugiem, stąd ``follow=True``.
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

    pierwsza = client.get(url, HTTP_HOST=site1.domain, follow=True)
    assert pierwsza.status_code == 200
    assert pierwsza["X-BPP-Cache"] == "MISS"

    druga = client.get(url, HTTP_HOST=site1.domain, follow=True)
    assert druga["X-BPP-Cache"] == "HIT", (
        "Strona rekordu nie trafiła do cache'a — najpewniej bezpiecznik "
        "CSRF odrzuca jej treść."
    )


@pytest.mark.django_db
def test_query_string_rozroznia_klucze(cache_locmem, site1, uczelnia1):
    """Paginacja (``?page=2``) nie może kolidować ze stroną pierwszą."""
    r1 = make_request_for_site(site1, path="/bpp/rok/2020/")
    r2 = make_request_for_site(site1, path="/bpp/rok/2020/?page=2")

    assert _klucz(r1) != _klucz(r2)


@pytest.mark.django_db
def test_baker_rekord_widoczny_po_inwalidacji(
    client,
    cache_locmem,
    site1,
    uczelnia1,
    jednostka_uczelnia1,
    tytuly,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Nowy autor pojawia się na liście autorów bez czekania na TTL."""
    url = reverse("bpp:browse_autorzy")

    client.get(url, HTTP_HOST=site1.domain)
    assert client.get(url, HTTP_HOST=site1.domain)["X-BPP-Cache"] == "HIT"

    with django_capture_on_commit_callbacks(execute=True):
        baker.make(
            "bpp.Autor",
            imiona="Nowy",
            nazwisko="Nowakowski",
            aktualna_jednostka=jednostka_uczelnia1,
        )

    po = client.get(url, HTTP_HOST=site1.domain)
    assert po["X-BPP-Cache"] == "MISS"
