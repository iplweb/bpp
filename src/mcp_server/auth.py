"""Weryfikacja bearera przed aplikacją MCP.

SDK MCP montuje ``RequireAuthMiddleware`` wyłącznie przy podanym
``token_verifier``, a ten odrzuca 401-ką KAŻDE żądanie bez tożsamości — czyli
wyklucza dostęp anonimowy, na którym nam zależy. Stąd własna warstwa
(spec §5.4).
"""

from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from django.db import close_old_connections

from mcp_server.kontekst import schemat_zadania

WYMAGANY_SCOPE = "read"


def _sprawdz(raw: str, zasob: str) -> bool:
    """Czy token jest ważny wg TYCH SAMYCH reguł, co DRF.

    ``StrictOAuth2Authentication`` wymaga ważnego tokenu, aktywnego konta ORAZ
    scope'u ``read``. Sprawdzanie tu mniej oznaczałoby, że token bez scope'u
    przechodzi bramkę i pada dopiero w DRF — czyli wraca jako błąd w treści
    JSON-RPC z HTTP 200, a klient nigdy nie ponawia autoryzacji.

    ``zasob`` to kanoniczny adres serwera MCP dla BIEŻĄCEGO żądania
    (``<schemat>://<host>/mcp``) — audience w rozumieniu RFC 8707. Sprawdzamy
    je, bo deklarujemy je w dokumencie PRM (``oauth_mcp.views_metadata``):
    deklaracja bez egzekwowania jest gorsza niż jej brak. Bez tego token
    zawężony do hosta jednej uczelni przechodziłby bramkę pod hostem drugiej.
    Semantykę dopasowania (origin, nie prefiks ścieżki) i powód tego wyboru
    opisuje ``oauth_mcp.audience``.

    Wyszukanie tokenu oddajemy walidatorowi DOT (``_load_access_token``)
    zamiast pisać własny ``filter(token=raw)``. Powody, oba istotne:

    * ``token`` to NIEZINDEKSOWANY ``TextField``; indeksowaną (i ``unique``)
      kolumną jest ``token_checksum`` (``oauth2_provider/models.py``). Filtr po
      ``token`` skanował całą tabelę tokenów, więc tani flood błędnymi
      bearerami obciążał bazę — na publicznym, nieuwierzytelnionym endpoincie.
    * Sposób liczenia checksumy (sha256 hex z UTF-8) oraz obsługa trybu
      „hashed at rest" (``COMPLIANT_BCP_RFC9700_TOKEN_STORAGE``, przy którym
      kolumna ``token`` jest PUSTA i wyszukanie po niej nie znalazłoby nic)
      są szczegółem DOT. Zduplikowane u nas rozjechałyby się przy pierwszej
      zmianie w pakiecie — a rozjazd oznaczałby cichą odmowę dostępu wszystkim.

    Klasę walidatora bierzemy z ``oauth2_settings``, nie zaszywamy
    ``OAuth2Validator`` — projekt może ją podmienić i wtedy bramka ma iść tą
    samą drogą, co DRF.
    """
    from oauth2_provider.settings import oauth2_settings

    close_old_connections()  # poza cyklem żądania Django — brak sygnałów
    try:
        token = oauth2_settings.OAUTH2_VALIDATOR_CLASS()._load_access_token(raw)
        if token is None or not token.is_valid():
            return False
        if token.user is None or not token.user.is_active:
            return False
        if not token.allows_audience(zasob):
            return False
        return bool(token.allow_scopes([WYMAGANY_SCOPE]))
    finally:
        close_old_connections()


zweryfikuj_token = sync_to_async(_sprawdz, thread_sensitive=False)


class BramkaBearera:
    """Przepuszcza anonima (gdy wolno) i odrzuca nieważny token 401-ką."""

    def __init__(self, aplikacja, *, wymagany: bool) -> None:
        self._aplikacja = aplikacja
        self._wymagany = wymagany

    async def __call__(self, scope, receive, send):
        naglowki = {k.lower(): v for k, v in scope.get("headers", [])}
        surowy = naglowki.get(b"authorization", b"").decode(errors="replace")
        schemat, _, wartosc = surowy.partition(" ")

        if not surowy:
            if self._wymagany:
                await self._odmow(scope, send)
                return
            await self._aplikacja(scope, receive, send)
            return

        if schemat.lower() != "bearer" or not await zweryfikuj_token(
            wartosc.strip(), self._zasob(scope)
        ):
            await self._odmow(scope, send)
            return

        await self._aplikacja(scope, receive, send)

    @staticmethod
    def _naglowki(scope) -> dict[str, str]:
        """Nagłówki ASGI jako słownik ``str``→``str``.

        Klucze ASGI są BAJTAMI — bez ``.decode()`` na kluczu każde
        ``get("host", …)`` z napisowym kluczem chybia i zawsze trafia w wartość
        domyślną. ``errors="replace"`` na wartości: nagłówek to dane od klienta,
        nie coś, czemu ufamy jako poprawnemu UTF-8 (ta sama decyzja co w
        ``routing.RouterHttp._dane``).
        """
        return {
            k.lower().decode(): v.decode(errors="replace")
            for k, v in scope.get("headers", [])
        }

    @classmethod
    def _zasob(cls, scope) -> str:
        """Kanoniczny adres serwera MCP dla tego żądania (audience RFC 8707).

        Ten sam adres, który ``oauth_mcp.views_metadata`` publikuje w PRM jako
        ``resource`` i który klient MCP wysyła w ``resource=`` przy autoryzacji.
        Host i schemat czytamy z nagłówków tak samo jak ``_odmow`` (jedno
        źródło prawdy: ``schemat_zadania``), a nie z ``dane_zadania`` —
        ``BramkaBearera`` bywa używana samodzielnie, bez ustawionego kontekstu.
        """
        naglowki = cls._naglowki(scope)
        host = naglowki.get("host", "localhost")
        schemat = schemat_zadania(naglowki, scope.get("scheme", "http"))
        return f"{schemat}://{host}/mcp"

    async def _odmow(self, scope, send) -> None:
        naglowki = self._naglowki(scope)
        host = naglowki.get("host", "localhost")
        # NIE ``scope["scheme"]``: nginx stoi w osobnym kontenerze, a
        # ``docker/appserver/gunicorn_conf.py`` nie ustawia
        # ``forwarded_allow_ips`` (default gunicorna to 127.0.0.1), więc
        # uvicorn NIE ufa nagłówkom proxy i zostawia scheme="http". PRM
        # wskazywałby wtedy na ``http://`` i psuł discovery OAuth — czyli
        # dokładnie to, po co ten adres istnieje. Nagłówek czytamy tak samo
        # jak ``RouterHttp._dane`` (jedno źródło prawdy: ``schemat_zadania``).
        schemat = schemat_zadania(naglowki, scope.get("scheme", "http"))
        prm = f"{schemat}://{host}/.well-known/oauth-protected-resource"
        cialo = json.dumps(
            {
                "error": "invalid_token",
                "error_description": "Wymagany ważny token OAuth.",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (
                        b"www-authenticate",
                        f'Bearer resource_metadata="{prm}"'.encode(),
                    ),
                ],
            }
        )
        await send({"type": "http.response.body", "body": cialo})
