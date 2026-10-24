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


def ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    """False dla adresów, na które NIE wolno kierować żądań:
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
