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
        from oauth2_provider.models import get_access_token_model

        AccessToken = get_access_token_model()
        tok = AccessToken.objects.filter(token=raw).first()
        return bool(tok and tok.is_valid())
