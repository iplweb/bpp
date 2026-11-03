"""Limit liczby zakończonych zgłoszeń publikacji w oknie godzinowym.

Klucz limitu: zalogowany użytkownik — jego konto (``user:<pk>``), anonim —
IP klienta wyznaczone przez ``django_bpp.client_ip.get_client_ip`` (ostatni
wpis X-Forwarded-For doklejony przez nginx). Zalogowani nie są liczeni per
IP, żeby pracownicy za wspólnym NAT-em uczelni nie blokowali się nawzajem.

Licznik żyje w domyślnym cache (Redis w produkcji): ``cache.add`` zakłada
klucz z TTL 1 h (okno stałe od pierwszego zgłoszenia), ``cache.incr`` jest
atomowy, więc równoległe żądania nie przekroczą limitu.

Limity (env, 0 = brak limitu): ``settings.ZGLOS_LIMIT_NA_GODZINE`` dla
anonimów (domyślnie 5) i ``settings.ZGLOS_LIMIT_NA_GODZINE_ZALOGOWANI`` dla
zalogowanych (domyślnie 10).
"""

import logging

from django.conf import settings
from django.core.cache import cache

from django_bpp.client_ip import get_client_ip

logger = logging.getLogger(__name__)

OKNO_SEKUNDY = 60 * 60

KOMUNIKAT_LIMIT_ZGLOSZEN = (
    "Przekroczono limit zgłoszeń publikacji na godzinę. Spróbuj ponownie "
    "później lub skontaktuj się z zespołem Biblioteki."
)


def _zalogowany(request):
    user = getattr(request, "user", None)
    return user is not None and user.is_authenticated


def limit_na_godzine(request):
    if _zalogowany(request):
        return getattr(settings, "ZGLOS_LIMIT_NA_GODZINE_ZALOGOWANI", 0) or 0
    return getattr(settings, "ZGLOS_LIMIT_NA_GODZINE", 0) or 0


def klucz_limitu(request):
    if _zalogowany(request):
        return f"zglos_publikacje:limit:user:{request.user.pk}"
    ip = get_client_ip(request) or "brak-ip"
    return f"zglos_publikacje:limit:ip:{ip}"


def limit_wyczerpany(request):
    """Czy limit jest już wyczerpany (odczyt, bez zwiększania licznika)."""
    limit = limit_na_godzine(request)
    if limit <= 0:
        return False
    return (cache.get(klucz_limitu(request)) or 0) >= limit


def zarezerwuj_zgloszenie(request):
    """Atomowo policz jedno zgłoszenie. Zwraca False, gdy limit przekroczony.

    Gdy cache nie wspiera liczników (np. DummyCache w dev), zgłoszenie jest
    przepuszczane, a problem logowany.
    """
    limit = limit_na_godzine(request)
    if limit <= 0:
        return True
    klucz = klucz_limitu(request)
    for _proba in range(2):
        cache.add(klucz, 0, timeout=OKNO_SEKUNDY)
        try:
            return cache.incr(klucz) <= limit
        except ValueError:
            # Klucz wygasł między add a incr (albo cache bez liczników) —
            # jedna ponowna próba z nowym oknem.
            continue
    logger.warning(
        "zglos_publikacje: cache nie obsługuje licznika limitu zgłoszeń "
        "— limit nieaktywny dla tego żądania"
    )
    return True
