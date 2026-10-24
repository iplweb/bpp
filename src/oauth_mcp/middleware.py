from django.http import JsonResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class ApiReadOnlyForBearerMiddleware:
    """Blokuje mutacje `/api/v1/` wykonane tokenem OAuth (MVP read-only).

    Auth DRF biegnie w widoku (po middleware), więc tu wykrywamy bearer po
    nagłówku i sami weryfikujemy token, zamiast polegać na `request.auth`
    (jeszcze nieustawionym). To warstwa nieobchodzona przez per-view
    `permission_classes` (spec §5.4b / B-2).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/api/v1/")
            and request.method not in SAFE_METHODS
            and self._ma_wazny_bearer(request)
        ):
            return JsonResponse(
                {"detail": "Zapis przez token MCP jest wyłączony (read-only)."},
                status=403,
            )
        return self.get_response(request)

    @staticmethod
    def _ma_wazny_bearer(request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.lower().startswith("bearer "):
            return False
        raw = header.split(" ", 1)[1].strip()
        if not raw:
            return False
        from oauth2_provider.settings import oauth2_settings

        # Ten sam lookup co DRF i bramka MCP (``mcp_server.auth``): walidator
        # DOT szuka po indeksowanym ``token_checksum`` i obsługuje tryb
        # hashowania tokenów (COMPLIANT_BCP_RFC9700_TOKEN_STORAGE), w którym
        # kolumna ``token`` jest pusta.
        tok = oauth2_settings.OAUTH2_VALIDATOR_CLASS()._load_access_token(raw)
        return bool(tok and tok.is_valid())
