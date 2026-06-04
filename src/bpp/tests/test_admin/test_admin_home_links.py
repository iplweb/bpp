"""Regresyjny test linków na "domowej" stronie admina (/admin/).

Łapie sytuacje typu: ktoś przemianował aplikację Django (np.
``dynamic_columns`` → ``dynamic_admin_columns``), a w menu / dashboardzie
został wpisany stary URL → 404 dla superusera klikającego z home page.

Podział na trzy testy (świadomy, pod CI):

* ``test_admin_changelist_reachable[<url>]`` — JEDEN case na zarejestrowany
  ModelAdmin, lista URL-i policzona w collection-time z ``admin.site._registry``
  (bez bazy). To jest ciężki bulk (rendering changelist), a parametryzacja
  pozwala pytest-split rozrzucić te ~N case'ów po wszystkich shardach i xdist
  po workerach. Wcześniej całe sondowanie siedziało w jednym ``transaction=True``
  teście (~116s wg ``.test_durations``) — pytest-split nigdy nie rozdzieli
  pojedynczego testu, więc był on twardą podłogą swojego sharda niezależnie od
  liczby shardów (305s na shardzie 0 przy 8 i przy 12 shardach).
* ``test_admin_add_form_reachable[<url>]`` — analogicznie JEDEN case na model
  dla add-formy (też potrafi być ciężka: autocomplete / inline widgety), też
  rozłożone po shardach. Akceptuje 403 (model z wyłączonym dodawaniem).
* ``test_admin_home_links_resolve_and_custom_reachable`` — lekki: pobiera
  /admin/ RAZ, a każdy wyrenderowany link MUSI się resolvować do widoku (to
  łapie stale URL po przemianowaniu aplikacji — ``resolve()`` jest in-process,
  bez renderingu). Changelisty i add-formy pokrywają testy parametryzowane
  powyżej, więc tu HTTP-em sondujemy tylko nieliczne linki spoza registry
  (realnie custom admin views) — dzięki czemu test zostaje tani.
"""

import re
from html.parser import HTMLParser

import pytest
from django.test import Client
from django.urls import Resolver404, resolve

# Linki, które celowo pomijamy w teście:
#  * logout — wylogowuje sesję klienta, w środku przebiegu testu nie ma
#    sensu sprawdzać (po nim wszystkie kolejne requesty byłyby 302→login).
#  * zewnętrzne usługi obsługiwane przez reverse-proxy (grafana, dozzle,
#    flower, importer_publikacji) — w testach nie biegną i 404/502 z nich
#    jest oczekiwane, a nie regresją w Pythonie.
_SKIP_PREFIXES = (
    "/admin/logout/",
    "/grafana/",
    "/dozzle/",
    "/flower/",
    "/importer_publikacji/",
)

# Linki do konkretnych rekordów (changelist „Ostatnie działania" itp.):
# w świeżej testowej bazie obiektów nie ma, więc 404 byłby fałszywy.
_RECORD_SPECIFIC = re.compile(r"^/admin/[^/]+/[^/]+/\d+/(change|history|delete)/")


class _AnchorHrefExtractor(HTMLParser):
    """Wyciąga href tylko z tagów <a> — pomija <link>/<script>/<img>."""

    def __init__(self):
        super().__init__()
        self.hrefs: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.add(value)
                return


def _extract_links(html_bytes):
    """Zwraca posortowaną listę unikalnych ścieżek klikalnych (<a href>)."""
    html = html_bytes.decode("utf-8", errors="replace")
    parser = _AnchorHrefExtractor()
    parser.feed(html)

    links = set()
    for href in parser.hrefs:
        # Obetnij fragment i query — interesuje nas sam path (resolve()
        # i tak nie przyjmuje query-stringa).
        href = href.split("#", 1)[0].split("?", 1)[0]
        # Zewnętrzne URL-e, javascript:, mailto:, puste — pomijamy.
        if not href or href.startswith(
            ("http://", "https://", "javascript:", "mailto:", "tel:")
        ):
            continue
        # Tylko URL-e absolutne („/...").
        if not href.startswith("/"):
            continue
        if href.startswith(_SKIP_PREFIXES):
            continue
        if _RECORD_SPECIFIC.match(href):
            continue
        links.add(href)

    return sorted(links)


def _registry_urls(action):
    """URL-e ``admin:<app>_<model>_<action>`` dla każdego zarejestrowanego
    ModelAdmin.

    Liczone w collection-time, BEZ bazy danych — ``reverse()`` potrzebuje tylko
    załadowanego URLconf-u (pytest-django robi ``django.setup()`` + admin
    autodiscover zanim collection ruszy), a ``admin.site._registry`` jest wtedy
    już wypełniony. Dzięki temu pytest-split widzi N osobnych param-case'ów
    i rozkłada je po shardach.
    """
    from django.contrib import admin
    from django.urls import NoReverseMatch, reverse

    urls = set()
    for model in admin.site._registry:
        meta = model._meta
        try:
            urls.add(reverse(f"admin:{meta.app_label}_{meta.model_name}_{action}"))
        except NoReverseMatch:
            # ModelAdmin bez standardowego URL-a dla tej akcji (np. nadpisany
            # get_urls) — nieosiągalny przez reverse, pomijamy.
            continue
    return sorted(urls)


# Ewaluowane raz, w collection-time. Jeśli puste (teoretycznie nie powinno),
# parametryzacja dałaby zero case'ów — guard-test niżej pilnuje, że registry
# w ogóle coś zawiera.
_REGISTRY_CHANGELIST_URLS = _registry_urls("changelist")
_REGISTRY_ADD_URLS = _registry_urls("add")


def test_registry_admin_urls_nonempty():
    """Sanity: collection-time enumeracja faktycznie coś znalazła.

    Gdyby admin autodiscover nie zadziałał, parametryzacje changelist/add
    zwinęłyby się do zera case'ów i CI przeszłoby „zielono" nic nie
    sprawdzając — ten guard temu zapobiega.
    """
    assert _REGISTRY_CHANGELIST_URLS, (
        "admin.site._registry nie dał żadnego changelist URL — autodiscover "
        "adminów nie zadziałał albo żaden ModelAdmin nie jest zarejestrowany."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("url", _REGISTRY_CHANGELIST_URLS)
def test_admin_changelist_reachable(admin_user, url):
    """Changelist zarejestrowanego ModelAdmin otwiera się bez 4xx/5xx.

    Jeden case na model → pytest-split rozkłada renderowanie changelist po
    shardach. ``transaction=True`` (jak w starym monolicie) jest NIEpotrzebne:
    tu jest jeden klient w jednym wątku, więc standardowy TX-rollback testu
    wystarcza i jest szybszy niż flush bazy per case.
    """
    client = Client()
    client.force_login(admin_user)
    response = client.get(url)
    assert response.status_code < 400, f"{url} -> HTTP {response.status_code}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", _REGISTRY_ADD_URLS)
def test_admin_add_form_reachable(admin_user, url):
    """Add-forma zarejestrowanego ModelAdmin renderuje się (lub jest celowo
    wyłączona).

    Też rozłożone po shardach (add-formy potrafią być ciężkie: autocomplete /
    inline widgety). Akceptujemy 403 — to znaczy, że ``has_add_permission``
    celowo wyłącza dodawanie dla tego modelu (taki model po prostu nie pokazuje
    linku „+ Dodaj" w menu); 404/500 to realna regresja i ma failować.
    """
    client = Client()
    client.force_login(admin_user)
    response = client.get(url)
    assert response.status_code < 400 or response.status_code == 403, (
        f"{url} -> HTTP {response.status_code}"
    )


@pytest.mark.django_db
def test_admin_home_links_resolve_and_custom_reachable(admin_user):
    """Każdy link ze strony /admin/ resolvuje się; custom/add-linki też 200.

    Łapie regresje typu: stale URL w menu po przemianowaniu aplikacji
    (``resolve()`` rzuca ``Resolver404`` → fail). Changelisty i add-formy
    zarejestrowanych modeli NIE są tu ponownie sondowane HTTP-em — pokrywają je
    rozłożone po shardach ``test_admin_changelist_reachable[...]`` i
    ``test_admin_add_form_reachable[...]`` — więc ten test zostaje tani (jeden
    GET /admin/ + resolve in-process + sondowanie tylko nielicznych linków
    spoza registry, czyli realnie custom admin views).

    Nie podążamy za przekierowaniami: 3xx do widoku w admin jest OK, bo to sam
    URL z menu sprawdzamy — nie cały graf nawigacji.
    """
    client = Client()
    client.force_login(admin_user)
    home = client.get("/admin/")
    assert home.status_code == 200, "/admin/ nie zwraca 200"

    # /admin/ już sprawdzone; pomiń żeby nie strzelać ponownie po linku
    # z breadcrumb logo.
    links = [link for link in _extract_links(home.content) if link != "/admin/"]
    assert links, (
        "Nie znaleziono żadnych linków na stronie /admin/ — test nic by nie sprawdził."
    )

    covered = set(_REGISTRY_CHANGELIST_URLS) | set(_REGISTRY_ADD_URLS)
    unresolvable = []
    broken = []
    for link in links:
        try:
            resolve(link)
        except Resolver404:
            unresolvable.append(link)
            continue
        # Changelisty i add-formy registry pokrywają rozłożone testy
        # parametryzowane — tu sonduj HTTP-em tylko linki spoza tej puli
        # (realnie custom admin views), żeby ten test został tani.
        if link not in covered:
            status = client.get(link).status_code
            if status >= 400:
                broken.append((link, status))

    assert not unresolvable, (
        "Linki ze strony /admin/, które NIE resolvują się do żadnego widoku "
        "(prawdopodobnie stale URL po przemianowaniu aplikacji):\n"
        + "\n".join(f"  {url}" for url in unresolvable)
    )
    assert not broken, (
        "Linki ze strony /admin/ (spoza registry-changelist), które zwróciły "
        "4xx/5xx:\n" + "\n".join(f"  {url} -> HTTP {code}" for url, code in broken)
    )
