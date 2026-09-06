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

WYMAGANY_SCOPE = "read"


def _sprawdz(raw: str) -> bool:
    """Czy token jest ważny wg TYCH SAMYCH reguł, co DRF.

    ``StrictOAuth2Authentication`` wymaga ważnego tokenu, aktywnego konta ORAZ
    scope'u ``read``. Sprawdzanie tu mniej oznaczałoby, że token bez scope'u
    przechodzi bramkę i pada dopiero w DRF — czyli wraca jako błąd w treści
    JSON-RPC z HTTP 200, a klient nigdy nie ponawia autoryzacji.
    """
    from oauth2_provider.models import get_access_token_model

    close_old_connections()  # poza cyklem żądania Django — brak sygnałów
    try:
        token = (
            get_access_token_model()
            .objects.select_related("user")
            .filter(token=raw)
            .first()
        )
        if token is None or not token.is_valid():
            return False
        if token.user is None or not token.user.is_active:
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

        if schemat.lower() != "bearer" or not await zweryfikuj_token(wartosc.strip()):
            await self._odmow(scope, send)
            return

        await self._aplikacja(scope, receive, send)

    async def _odmow(self, scope, send) -> None:
        naglowki = {k.lower(): v for k, v in scope.get("headers", [])}
        host = naglowki.get(b"host", b"localhost").decode()
        schemat = "https" if scope.get("scheme") in ("https", "wss") else "http"
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
