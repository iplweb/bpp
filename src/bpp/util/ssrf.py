"""Walidacja adresów usług zewnętrznych (ochrona przed SSRF).

Wspólna logika oceny adresów IP — używana przez importer publikacji
(``importer_publikacji.providers.www.network``) oraz przez walidację adresów
integracji w ``Uczelnia`` (PBN, DSpace).

Moduł celowo NIE podmienia ``socket.getaddrinfo`` (to robi wyłącznie importer
na potrzeby pinowania połączeń), więc można go bezpiecznie importować z
modeli.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _osadzone_ipv4(ip: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    """Adresy IPv4 osadzone w adresie IPv6 (IPv4-mapped, 6to4, Teredo,
    NAT64 ``64:ff9b::/96``) — oceniamy je tak, jak sam adres IPv4."""
    if ip.ipv4_mapped is not None:
        return [ip.ipv4_mapped]
    if ip.sixtofour is not None:
        return [ip.sixtofour]
    if ip.teredo is not None:
        return list(ip.teredo)
    if ip in _NAT64:
        return [ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)]
    return []


def ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    """True tylko dla adresów globalnych (``is_global``). False m.in. dla:
    prywatnych (10/8, 172.16/12, 192.168/16, fc00::/7), CGNAT 100.64/10,
    loopback (127/8, ::1), link-local (169.254/16 — w tym metadata cloud
    169.254.169.254), multicast, zarezerwowanych i ``0.0.0.0``. Adresy IPv6
    z osadzonym IPv4 (IPv4-mapped, 6to4, Teredo, NAT64) są oceniane po
    osadzonym adresie IPv4.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        osadzone = _osadzone_ipv4(ip)
        if osadzone:
            return all(ip_is_public(v4) for v4 in osadzone)
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return False
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_ips(hostname: str) -> list[str]:
    """Rozwiąż host na listę adresów IP (v4 i v6). Wydzielony seam — testy
    podmieniają go zamiast globalnego ``socket.getaddrinfo``."""
    infos = socket.getaddrinfo(hostname, None)
    return [info[4][0] for info in infos]


def _ip_literal(hostname: str):
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def _dozwolone_schematy() -> tuple[str, ...]:
    if settings.DEBUG:
        return ("https", "http")
    return ("https",)


def waliduj_url_integracji_offline(url: str) -> None:
    """Sprawdź schemat i — gdy host jest literałem IP — czy adres jest
    publiczny. Nie wykonuje zapytań DNS. Rzuca ``ValidationError``."""
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in _dozwolone_schematy():
        raise ValidationError("Adres musi zaczynać się od https://.")
    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("Adres nie zawiera nazwy hosta.")
    ip = _ip_literal(hostname)
    if ip is not None and not ip_is_public(ip):
        raise ValidationError(
            "Adres musi wskazywać na publicznie dostępny serwer "
            "(adresy lokalne, prywatne i link-local są niedozwolone)."
        )


def waliduj_url_integracji(url: str) -> None:
    """Pełna walidacja adresu integracji: jak
    ``waliduj_url_integracji_offline`` plus rozwiązanie nazwy hosta w DNS
    i sprawdzenie, że KAŻDY zwrócony adres jest publiczny (fail-closed)."""
    if not url:
        return
    waliduj_url_integracji_offline(url)
    hostname = urlparse(url).hostname
    if _ip_literal(hostname) is not None:
        return
    try:
        ips = resolve_ips(hostname)
    except (socket.gaierror, UnicodeError, ValueError):
        raise ValidationError(
            f"Nie można rozwiązać nazwy hosta „{hostname}”."
        ) from None
    if not ips:
        raise ValidationError(f"Nie można rozwiązać nazwy hosta „{hostname}”.")
    for ip_str in ips:
        ip = _ip_literal(ip_str)
        if ip is None or not ip_is_public(ip):
            raise ValidationError(
                f"Host „{hostname}” rozwiązuje się na adres niepubliczny — "
                "adres musi wskazywać na publicznie dostępny serwer."
            )
