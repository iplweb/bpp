"""Pobieranie strony WWW + walidacja URL (z ochroną przed SSRF)."""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

FETCH_TIMEOUT = 15

#: Ile przekierowań śledzimy ręcznie. Każdy hop jest walidowany osobno
#: (``allow_redirects=False`` + ponowny ``_host_is_safe``), więc redirect na
#: adres wewnętrzny nie omija guardu SSRF.
MAX_REDIRECTS = 5


def _resolve_ips(hostname: str) -> list[str]:
    """Rozwiąż host na listę adresów IP (v4 i v6). Wydzielony seam — testy
    podmieniają go zamiast globalnego ``socket.getaddrinfo`` (co zepsułoby
    rozwiązywanie hosta bazy w testcontainers)."""
    infos = socket.getaddrinfo(hostname, None)
    return [info[4][0] for info in infos]


def _ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    """False dla adresów, na które NIE wolno kierować importerowi:
    prywatne (10/8, 172.16/12, 192.168/16, fc00::/7, CGNAT), loopback
    (127/8, ::1), link-local (169.254/16 — w tym metadata cloud
    169.254.169.254), multicast, zarezerwowane i ``0.0.0.0``.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        # ::ffff:127.0.0.1 i pokrewne — oceniaj po zmapowanym adresie v4.
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_is_safe(hostname: str | None) -> bool:
    """True tylko gdy KAŻDY adres, na który rozwiązuje się host, jest publiczny.

    Fail-closed: brak hosta, błąd DNS, brak wyników lub choćby jeden
    nie-publiczny adres → False (blokujemy). Chroni przed SSRF na loopback,
    sieci prywatne i endpointy metadata (169.254.169.254), także gdy host
    to nazwa DNS rozwiązywana do sieci wewnętrznej.
    """
    if not hostname:
        return False
    try:
        ips = _resolve_ips(hostname)
    except (socket.gaierror, UnicodeError, ValueError):
        return False
    if not ips:
        return False
    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if not _ip_is_public(ip):
            return False
    return True


def safe_get(
    url: str,
    *,
    timeout: int = FETCH_TIMEOUT,
    headers: dict | None = None,
) -> requests.Response | None:
    """GET z ochroną SSRF — zwraca finalną odpowiedź 2xx albo ``None``.

    Waliduje host przed każdym requestem i po każdym przekierowaniu (śledzenie
    RĘCZNE, ``allow_redirects=False``), więc redirect ``https://public →
    http://127.0.0.1`` nie omija guardu. ``None`` gdy: host nie-publiczny,
    schemat inny niż http/https, błąd sieci, odpowiedź 4xx/5xx albo
    przekroczony limit przekierowań.

    Wspólny bezpieczny klient dla wszystkich providerów pobierających URL od
    użytkownika (WWW, DSpace, Omega-PSIR) — ochrona nie rozjeżdża się
    per-provider.
    """
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current)
            if parsed.scheme not in ("http", "https"):
                return None
            if not _host_is_safe(parsed.hostname):
                return None

            resp = requests.get(
                current,
                timeout=timeout,
                allow_redirects=False,
                headers=headers,
            )

            if 300 <= resp.status_code < 400:
                location = resp.headers.get("Location")
                if not location:
                    return None
                current = urljoin(current, location)
                continue

            resp.raise_for_status()
            return resp
    except requests.RequestException:
        return None
    # Wyczerpaliśmy limit przekierowań bez finalnej odpowiedzi.
    return None


def _fetch_page(
    url: str,
) -> tuple[str, BeautifulSoup] | None:
    """Pobierz stronę i zwróć (html, soup). SSRF-guard w ``safe_get``."""
    resp = safe_get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BPP-Importer/1.0)"},
    )
    if resp is None:
        return None
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    return html, soup


def _validate_url(url: str) -> str | None:
    """Waliduj i znormalizuj URL. None gdy URL jest niepoprawny albo wskazuje
    na adres nie-publiczny (SSRF guard — sprawdzane też ponownie przy fetchu)."""
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

    if not _host_is_safe(parsed.hostname):
        return None

    return url
