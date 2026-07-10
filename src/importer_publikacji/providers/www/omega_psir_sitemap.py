"""Detekcja i pobranie listy artykułów z eksportu XML Omega-PSIR.

Instancje platformy Omega-PSIR (np. PPM UMLUB — ``ppm.umlub.pl``)
publikują w ``robots.txt`` SEO-sitemapę (``<host>/years-xml.seam`` jako
indeks, a pod nim per-rok ``<host>/articles-xml.seam?year=YYYY``) z
listą URL-i stron szczegółowych artykułów (``/info/article/{id}``).

To jedyna **stateless** (bez JS/ViewState) droga do listy prac
znaleziona podczas spike'u Track C — w przeciwieństwie do
``globalResultList.seam`` (siatka wyników wyszukiwania), która jest
renderowana AJAX-em JSF/Seam i wymaga statefulnego
``javax.faces.ViewState``, którego ``requests.get`` nie odtworzy.
Szczegóły: ``docs/superpowers/handoffs/2026-07-10-ppm-lista-spike-findings.md``.

URL-e zwrócone stąd trafiają do ``WWWProvider.fetch()``, który już
rozpoznaje kształt ``/info/article/{id}`` (``omega_psir.py``) i
parsuje ``citation_*``/JSON-LD z tych stron.
"""

import re
from urllib.parse import parse_qs, urlparse

import defusedxml.ElementTree as ElementTree
import requests
from defusedxml.common import DefusedXmlException

FETCH_TIMEOUT = 15

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Ścieżka eksportu XML listy artykułów (rozpoznanie po kształcie URL,
# tak jak OMEGA_ARTICLE_RE w omega_psir.py — bez allow-listy hostów).
ARTICLES_SITEMAP_PATH_RE = re.compile(r"/articles-xml\.seam$")
YEAR_RE = re.compile(r"^\d{4}$")


def _detect_omega_articles_sitemap(url: str) -> str | None:
    """Rozpoznaj URL eksportu XML listy artykułów Omega-PSIR.

    Wymaga ścieżki ``/articles-xml.seam`` + parametru ``year=YYYY``.
    Zwraca ten sam URL (do dalszego fetch'u) albo ``None``.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not ARTICLES_SITEMAP_PATH_RE.search(parsed.path):
        return None
    years = parse_qs(parsed.query).get("year")
    if not years or not YEAR_RE.match(years[0]):
        return None
    return url


def _fetch_omega_articles_sitemap(url: str) -> list[str] | None:
    """Pobierz i sparsuj eksport XML — zwróć listę URL-i stron szczegółowych.

    ``None`` przy błędzie sieci/HTTP/parsowania — wołający ma wtedy
    spaść do zachowania domyślnego (1 rekord), a nie wyrzucić wyjątek
    do widoku.
    """
    try:
        resp = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BPP-Importer/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    try:
        root = ElementTree.fromstring(resp.content)
    except (ElementTree.ParseError, DefusedXmlException):
        return None

    urls = [
        loc.text.strip()
        for loc in root.findall(".//sm:url/sm:loc", SITEMAP_NS)
        if loc.text and loc.text.strip()
    ]
    return urls or None
