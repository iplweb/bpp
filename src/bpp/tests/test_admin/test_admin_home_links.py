"""Regresyjny test linków na "domowej" stronie admina (/admin/).

Łapie sytuacje typu: ktoś przemianował aplikację Django (np.
``dynamic_columns`` → ``dynamic_admin_columns``), a w menu / dashboardzie
został wpisany stary URL → 404 dla superusera klikającego z home page.
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor
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


# Liczba wątków sprawdzających linki równolegle. Empirycznie 4–6 to plateau
# na M-Mac (~45–47s end-to-end); 8 wątków ~58s, 16 wątków ~113s. Plateau jest
# tam, bo template rendering w adminie jest w przewadze CPU-bound w Pythonie,
# więc GIL serializuje pracę zanim conn pool PG zacznie być wąskim gardłem.
_PARALLELISM = 4


@pytest.mark.django_db(transaction=True)
@pytest.mark.timeout(600)
def test_admin_home_links_all_reachable(admin_user):
    """Każdy link ze strony /admin/ otwiera się bez 404/500.

    Łapie regresje typu: stale URL w menu po przemianowaniu aplikacji.
    Nie podążamy za przekierowaniami: 3xx do widoku w admin jest OK,
    bo to sam URL z menu sprawdzamy — nie cały graf nawigacji.

    `transaction=True` jest konieczne, żeby wątki sprawdzające linki widziały
    zacommitowanego `admin_user` przez własne połączenia do PG — przy
    standardowym TX-wrap teście inne wątki dostają pustą bazę i 302→login.
    """
    home_client = Client()
    home_client.force_login(admin_user)
    home = home_client.get("/admin/")
    assert home.status_code == 200, "/admin/ nie zwraca 200"

    links = _extract_links(home.content)
    assert links, (
        "Nie znaleziono żadnych linków na stronie /admin/ — "
        "test nic by nie sprawdził."
    )

    # /admin/ już sprawdzone; pomiń żeby nie strzelać ponownie po linku
    # z breadcrumb logo.
    links = [link for link in links if link != "/admin/"]

    tls = threading.local()

    def _probe(link):
        client = getattr(tls, "client", None)
        if client is None:
            client = Client()
            client.force_login(admin_user)
            tls.client = client
        response = client.get(link)
        return link, response.status_code

    broken = []
    with ThreadPoolExecutor(max_workers=_PARALLELISM) as executor:
        for link, status in executor.map(_probe, links):
            if status >= 400:
                broken.append((link, status))

    assert not broken, (
        "Linki ze strony /admin/, które zwróciły 4xx/5xx:\n"
        + "\n".join(f"  {url} -> HTTP {code}" for url, code in broken)
    )
