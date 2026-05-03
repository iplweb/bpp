"""Pobieranie strony WWW + walidacja URL."""

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

FETCH_TIMEOUT = 15


def _fetch_page(
    url: str,
) -> tuple[str, BeautifulSoup] | None:
    """Pobierz stronę i zwróć (html, soup)."""
    try:
        resp = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={
                "User-Agent": ("Mozilla/5.0 (compatible; BPP-Importer/1.0)"),
            },
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    return html, soup


def _validate_url(url: str) -> str | None:
    """Waliduj i znormalizuj URL."""
    url = url.strip()
    if not url:
        return None

    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if not parsed.scheme or not parsed.netloc:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    return url
