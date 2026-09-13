"""Klient USOS API (https://apps.usos.edu.pl/developers/api/).

USOS API to zwykły REST-owy GET zwracający JSON. Dwie rzeczy, które warto
wiedzieć zanim się to czyta:

1. **Każda uczelnia ma własną instalację** pod własnym ``base_url`` (lista:
   ``services/apisrv/installations``) i **własny consumer key**. Nie ma
   centralnego klucza „na BPP" — klucz wydaje administrator USOS danej
   uczelni.
2. **Autoryzacja to OAuth 1.0a**, nie 2.0. Część metod (``fac/*``) działa
   anonimowo, część (``users/staff_index``, ``users/user``) wymaga podpisania
   żądania consumer key, a dane wrażliwe (PESEL, historia zatrudnienia) —
   klucza administracyjnego.

Klient przyjmuje sesję przez konstruktor, żeby dało się go testować bez
mockowania ruchu sieciowego.
"""

import requests
from requests_oauthlib import OAuth1

DOMYSLNY_TIMEOUT = 30


class UsosApiError(Exception):
    """Błąd zgłoszony przez USOS API.

    USOS sygnalizuje błędy kodem HTTP 400 i ciałem JSON z kluczem ``message``
    (opcjonalnie ``error`` i ``reason``), np.::

        {"message": "Access to method denied. Consumer signature is required.",
         "error": "method_forbidden", "reason": "consumer_missing"}
    """

    def __init__(self, message, *, reason=None, status_code=None):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code


class UsosApiClient:
    def __init__(
        self,
        base_url,
        consumer_key=None,
        consumer_secret=None,
        session=None,
        timeout=DOMYSLNY_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout

    @property
    def anonimowy(self):
        """True, gdy klient nie ma consumer key (działają tylko metody otwarte)."""
        return not self.consumer_key

    def _auth(self):
        if self.anonimowy:
            return None
        # Domyślna metoda podpisu OAuth1 to HMAC-SHA1 — tej oczekuje USOS.
        return OAuth1(self.consumer_key, client_secret=self.consumer_secret)

    def call(self, method, **params):
        """Wywołuje metodę USOS API, np. ``call("services/fac/faculty", fac_id=...)``.

        Parametry o wartości ``None`` są pomijane, żeby wołający mógł
        przekazywać opcjonalne argumenty bez budowania słownika warunkowo.
        """
        url = f"{self.base_url}/{method.lstrip('/')}"
        params = {
            klucz: wartosc for klucz, wartosc in params.items() if wartosc is not None
        }

        response = self.session.get(
            url, params=params, timeout=self.timeout, auth=self._auth()
        )
        return self._przetworz_odpowiedz(response, method)

    def _przetworz_odpowiedz(self, response, method):
        try:
            dane = response.json()
        except ValueError:
            # Nieistniejąca metoda to 404 z pustym ciałem — bez tego wołający
            # dostałby surowy ValueError z dekodera JSON, bez informacji, która
            # metoda zawiodła.
            dane = None

        if response.status_code != 200:
            if isinstance(dane, dict):
                komunikat = dane.get("message") or response.text
                reason = dane.get("reason")
            else:
                komunikat = response.text or f"HTTP {response.status_code}"
                reason = None
            raise UsosApiError(
                f"{method}: {komunikat}",
                reason=reason,
                status_code=response.status_code,
            )

        return dane
