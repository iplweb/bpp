"""Regresyjny test linków na "domowej" stronie admina (/admin/).

Łapie sytuacje typu: ktoś przemianował aplikację Django (np.
``dynamic_columns`` → ``dynamic_admin_columns``), a w menu / dashboardzie
został wpisany stary URL → 404 dla superusera klikającego z home page.
"""

import re
from html.parser import HTMLParser

import pytest
from django.test import Client


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
    """Zwraca posortowaną listę unikalnych URL-i klikalnych (<a href>)."""
    html = html_bytes.decode("utf-8", errors="replace")
    parser = _AnchorHrefExtractor()
    parser.feed(html)

    links = set()
    for href in parser.hrefs:
        # Obetnij fragment i query — interesuje nas sam path.
        href = href.split("#", 1)[0]
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


@pytest.fixture
def admin_django_client(admin_user) -> Client:
    """Zalogowany superuser przez standardowy Django test client (bez webtest)."""
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_admin_home_page_loads(admin_django_client):
    """Sanity: sama strona /admin/ musi się otwierać."""
    response = admin_django_client.get("/admin/")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.timeout(600)
def test_admin_home_links_all_reachable(admin_django_client):
    """Każdy link ze strony /admin/ otwiera się bez 404/500.

    Łapie regresje typu: stale URL w menu po przemianowaniu aplikacji.
    Nie podążamy za przekierowaniami: 3xx do widoku w admin jest OK,
    bo to sam URL z menu sprawdzamy — nie cały graf nawigacji.
    """
    home = admin_django_client.get("/admin/")
    assert home.status_code == 200, "/admin/ nie zwraca 200"

    links = _extract_links(home.content)
    assert links, (
        "Nie znaleziono żadnych linków na stronie /admin/ — "
        "test nic by nie sprawdził."
    )

    broken = []
    for link in links:
        sub = admin_django_client.get(link)
        if sub.status_code >= 400:
            broken.append((link, sub.status_code))

    assert not broken, (
        "Linki ze strony /admin/, które zwróciły 4xx/5xx:\n"
        + "\n".join(f"  {url} -> HTTP {code}" for url, code in broken)
    )
