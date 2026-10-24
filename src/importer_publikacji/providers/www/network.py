"""Pobieranie strony WWW + walidacja URL (z ochroną przed SSRF)."""

import ipaddress
import socket
import threading
import time
from contextlib import contextmanager
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

FETCH_TIMEOUT = 15

#: Ile przekierowań śledzimy ręcznie. Każdy hop jest walidowany osobno
#: (``allow_redirects=False`` + ponowny ``_host_is_safe``), więc redirect na
#: adres wewnętrzny nie omija guardu SSRF.
MAX_REDIRECTS = 5

#: Twardy limit rozmiaru pobieranego ciała (10 MB). ``safe_get`` streamuje
#: odpowiedź i przerywa po przekroczeniu — bez tego ``resp.text`` ładowałby
#: całe ciało do pamięci (DoS na pamięć od kontrolowanego serwera).
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

#: Rozmiar porcji przy streamowaniu ciała.
_CHUNK = 64 * 1024

#: Całkowity budżet czasu na WSZYSTKIE hopy łącznie (redirecty + pobranie
#: ciała). ``FETCH_TIMEOUT`` jest per-request; bez tego łańcuch przekierowań
#: mógłby przeciągać połączenie w nieskończoność (N hopów × timeout).
TOTAL_DEADLINE = 30


# --- Pinowanie DNS (ochrona przed rebindingiem, TOCTOU) -------------------
#
# Walidacja rozwiązuje host raz (``_resolve_ips``) i sprawdza ``_ip_is_public``,
# ale ``requests``/``urllib3`` rozwiązałby nazwę PONOWNIE przy nawiązywaniu
# połączenia — osobny lookup. Złośliwy DNS z niskim TTL mógłby zwrócić adres
# publiczny przy walidacji, a loopback/prywatny/``169.254.169.254`` (metadata)
# przy realnym połączeniu.
#
# Pinujemy: zestaw adresów z walidacji jest jedynym, którego używa połączenie.
# Realizujemy to owijając ``socket.getaddrinfo`` (wołane przez urllib3 w
# ``create_connection``) w wersję świadomą thread-local mapy host->[IP].
# Nazwa hosta w URL pozostaje nietknięta, więc SNI (``server_hostname``),
# walidacja certyfikatu TLS i nagłówek ``Host`` są zachowane — pinujemy tylko
# warstwę rozwiązywania nazw, nie sam URL.

#: Realny resolver, zachowany przed podmianą. Osobny seam (testy mogą udawać
#: rebinding, podmieniając to na resolver zwracający adres wewnętrzny).
_system_getaddrinfo = socket.getaddrinfo

#: Thread-local mapa host->[IP] aktywna tylko w obrębie ``_pin_host``. Dzięki
#: thread-local pinowanie jednego wątku nie wpływa na równoległe połączenia.
_pin = threading.local()

_UNSET = object()


def _pinning_getaddrinfo(host, *args, **kwargs):
    """Owijka ``socket.getaddrinfo``: dla hostów pinowanych w tym wątku zwraca
    rozwiązanie po zweryfikowanym IP (numeryczne — bez sieciowego DNS);
    pozostałe delegują do realnego resolvera."""
    pinned = getattr(_pin, "hosts", None)
    if pinned and host in pinned:
        results = []
        for ip in pinned[host]:
            results.extend(_system_getaddrinfo(ip, *args, **kwargs))
        return results
    return _system_getaddrinfo(host, *args, **kwargs)


def _install_pinning_resolver():
    """Zainstaluj owijkę ``socket.getaddrinfo`` raz (idempotentnie)."""
    current = socket.getaddrinfo
    if getattr(current, "_bpp_ssrf_pin", False):
        return
    _pinning_getaddrinfo._bpp_ssrf_pin = True
    socket.getaddrinfo = _pinning_getaddrinfo


_install_pinning_resolver()


@contextmanager
def _pin_host(hostname: str, ips: list[str]):
    """Na czas bloku pinuj rozwiązywanie ``hostname`` do ``ips`` (w tym wątku).
    Zagnieżdżenie i współbieżność są bezpieczne (thread-local + restore)."""
    hosts = getattr(_pin, "hosts", None)
    if hosts is None:
        hosts = {}
        _pin.hosts = hosts
    prev = hosts.get(hostname, _UNSET)
    hosts[hostname] = ips
    try:
        yield
    finally:
        if prev is _UNSET:
            hosts.pop(hostname, None)
        else:
            hosts[hostname] = prev


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


def _safe_resolve(hostname: str | None) -> list[str] | None:
    """Rozwiąż host i zwróć listę adresów IP — ale TYLKO gdy każdy z nich jest
    publiczny; inaczej ``None`` (fail-closed).

    Zwrócony zestaw służy podwójnie: jako decyzja („wolno pobrać") oraz jako
    zestaw adresów do zapinowania połączenia (ten sam wynik rozwiązywania, bez
    drugiego lookupu → brak okna na DNS rebinding).

    Fail-closed: brak hosta, błąd DNS, brak wyników lub choćby jeden
    nie-publiczny adres → ``None``. Chroni przed SSRF na loopback, sieci
    prywatne i endpointy metadata (169.254.169.254), także gdy host to nazwa
    DNS rozwiązywana do sieci wewnętrznej.
    """
    if not hostname:
        return None
    try:
        ips = _resolve_ips(hostname)
    except (socket.gaierror, UnicodeError, ValueError):
        return None
    if not ips:
        return None
    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return None
        if not _ip_is_public(ip):
            return None
    return ips


def _host_is_safe(hostname: str | None) -> bool:
    """True tylko gdy KAŻDY adres, na który rozwiązuje się host, jest publiczny.

    Cienka nakładka na ``_safe_resolve`` (zachowana dla ``_validate_url`` i
    testów, które sprawdzają samą decyzję bez potrzeby listy adresów).
    """
    return _safe_resolve(hostname) is not None


#: Komunikat dla użytkownika, gdy URL ma niedozwolony schemat albo port.
HTTPS_ONLY_MESSAGE = (
    "Importer pobiera dane wyłącznie przez HTTPS na standardowym porcie 443. "
    "Podaj adres zaczynający się od „https://” bez numeru portu "
    "(adresy „http://” bez portu są automatycznie zamieniane na „https://”)."
)


def _is_https_443(parsed) -> bool:
    """True gdy sparsowany URL to ``https`` na porcie 443 (domyślnym albo
    jawnym). Niepoprawny port (``:abc``, ``:99999``) → False."""
    if parsed.scheme != "https":
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    return port in (None, 443)


def _https_only(url: str) -> str | None:
    """Znormalizuj URL do ``https`` na porcie 443 albo zwróć ``None``.

    * ``https://host/…`` lub ``https://host:443/…`` → bez zmian;
    * ``http://host/…`` lub ``http://host:80/…`` → ``https://host/…``
      (wygoda dla wklejanych starych linków);
    * każdy inny schemat albo port → ``None``.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if _is_https_443(parsed):
        return url
    if parsed.scheme != "http":
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port not in (None, 80) or not parsed.hostname:
        return None
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"  # IPv6 — przywróć nawiasy
    netloc = host
    if "@" in parsed.netloc:
        netloc = parsed.netloc.rsplit("@", 1)[0] + "@" + host
    return urlunparse(parsed._replace(scheme="https", netloc=netloc))


def url_transport_error(url: str) -> str | None:
    """Czytelny komunikat, gdy URL (z jawnym schematem) nie da się sprowadzić
    do ``https`` na porcie 443; ``None`` gdy schemat/port są w porządku albo
    URL nie ma schematu (o reszcie decyduje zwykła walidacja)."""
    url = (url or "").strip()
    if "://" not in url:
        return None
    if _https_only(url) is None:
        return HTTPS_ONLY_MESSAGE
    return None


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
    schemat/port inny niż ``https`` na 443 (na dowolnym hopie — bez
    downgrade'u do http), błąd sieci, odpowiedź 4xx/5xx albo przekroczony
    limit przekierowań. Przepisanie ``http://`` → ``https://`` robi wyłącznie
    walidacja wejścia (``_https_only``), nie ten klient.

    Utwardzenia poza samą walidacją hosta:

    * **pinowanie połączenia** do zweryfikowanego IP (zestaw z ``_safe_resolve``
      jest jedynym, jaki widzi połączenie) — zamyka okno na DNS rebinding
      (TOCTOU) między walidacją a realnym ``getaddrinfo`` urllib3;
    * **twardy limit rozmiaru ciała** (``MAX_RESPONSE_BYTES``) — streamujemy i
      przerywamy po przekroczeniu (DoS na pamięć);
    * **całkowity deadline** (``TOTAL_DEADLINE``) na wszystkie hopy łącznie,
      obok per-request ``timeout``.

    Wspólny bezpieczny klient dla wszystkich providerów pobierających URL od
    użytkownika (WWW, DSpace, Omega-PSIR) — ochrona nie rozjeżdża się
    per-provider.
    """
    current = url
    deadline = time.monotonic() + TOTAL_DEADLINE
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current)
            # Każdy hop (także przekierowanie) wyłącznie https na porcie 443
            # — bez downgrade'u do http i bez innych portów.
            if not _is_https_443(parsed):
                return None
            ips = _safe_resolve(parsed.hostname)
            if ips is None:
                return None

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            hop_timeout = min(timeout, remaining)

            # Pin obejmuje moment nawiązania połączenia (getaddrinfo urllib3).
            # Ciało czytamy już po connect — nie wymaga aktywnego pinu.
            with _pin_host(parsed.hostname, ips):
                resp = requests.get(
                    current,
                    timeout=hop_timeout,
                    allow_redirects=False,
                    headers=headers,
                    stream=True,
                )

            if 300 <= resp.status_code < 400:
                resp.close()
                location = resp.headers.get("Location")
                if not location:
                    return None
                current = urljoin(current, location)
                continue

            resp.raise_for_status()
            if not _read_capped_body(resp, deadline):
                return None
            return resp
    except requests.RequestException:
        return None
    # Wyczerpaliśmy limit przekierowań bez finalnej odpowiedzi.
    return None


def _read_capped_body(
    resp: requests.Response,
    deadline: float,
) -> bool:
    """Wczytaj ciało odpowiedzi z twardym limitem rozmiaru i deadline'em.

    Materializuje ``resp._content`` (żeby ``resp.text``/``resp.json()`` działały
    mimo ``stream=True``). Zwraca ``True`` przy sukcesie; ``False`` gdy ciało
    przekracza ``MAX_RESPONSE_BYTES`` albo deadline — wtedy zamyka ``resp``.
    """
    declared = resp.headers.get("Content-Length")
    if declared is not None:
        try:
            if int(declared) > MAX_RESPONSE_BYTES:
                resp.close()
                return False
        except ValueError:
            pass  # nagłówek śmieciowy — polegamy na twardym limicie niżej
    chunks = bytearray()
    try:
        for chunk in resp.iter_content(_CHUNK):
            if not chunk:
                continue
            chunks += chunk
            if len(chunks) > MAX_RESPONSE_BYTES:
                resp.close()
                return False
            if time.monotonic() > deadline:
                resp.close()
                return False
    except requests.RequestException:
        resp.close()
        return False
    resp._content = bytes(chunks)
    resp._content_consumed = True
    return True


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

    url = _https_only(url)
    if url is None:
        return None
    parsed = urlparse(url)

    if not _host_is_safe(parsed.hostname):
        return None

    return url
