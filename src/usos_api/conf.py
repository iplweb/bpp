"""Budowanie klienta USOS API z ustawień Django.

Ustawienia (wszystkie opcjonalne poza pierwszym):

``USOS_API_BASE_URL``
    Adres instalacji USOS API uczelni, np. ``https://usosapps.umlub.pl/``.
    Listę instalacji oddaje ``services/apisrv/installations`` instalacji
    referencyjnej.
``USOS_API_CONSUMER_KEY`` / ``USOS_API_CONSUMER_SECRET``
    Klucz wydawany przez administratora USOS **danej uczelni**. Bez niego
    klient działa anonimowo — wystarczy do struktury jednostek, nie
    wystarczy do danych pracowników.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from usos_api.client import UsosApiClient


def buduj_klienta(base_url=None, consumer_key=None, consumer_secret=None):
    """Buduje klienta; argumenty mają pierwszeństwo przed ustawieniami."""
    base_url = base_url or getattr(settings, "USOS_API_BASE_URL", None)
    if not base_url:
        raise ImproperlyConfigured(
            "Brak adresu instalacji USOS API — ustaw USOS_API_BASE_URL albo "
            "podaj --base-url."
        )

    return UsosApiClient(
        base_url,
        consumer_key=consumer_key or getattr(settings, "USOS_API_CONSUMER_KEY", None),
        consumer_secret=(
            consumer_secret or getattr(settings, "USOS_API_CONSUMER_SECRET", None)
        ),
    )
