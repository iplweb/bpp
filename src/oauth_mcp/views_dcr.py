import json
import re

from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_application_model

# Allowlista wzorców redirect_uri (spec §5.6): callbacki Claude + lokalne.
_ALLOWED_REDIRECT_PATTERNS = [
    re.compile(r"^https://claude\.ai/[^\s]*$"),
    re.compile(r"^https://[a-z0-9.-]+\.claude\.ai/[^\s]*$"),
    re.compile(r"^https://claude\.com/[^\s]*$"),
    re.compile(r"^http://localhost(:\d+)?/[^\s]*$"),
    re.compile(r"^http://127\.0\.0\.1(:\d+)?/[^\s]*$"),
]


def _dozwolony(uri: str) -> bool:
    return any(p.match(uri) for p in _ALLOWED_REDIRECT_PATTERNS)


@method_decorator(csrf_exempt, name="dispatch")
class DynamicClientRegistrationView(View):
    """RFC 7591 — rejestracja publicznego klienta MCP (public + PKCE).

    Otwarta rejestracja z twardymi limitami (spec §5.6/§8/W7): allowlista
    redirect_uri, bez auto-approve dla nieznanych wzorców. Rate-limit ręczny
    przez cache (to nie DRF view, więc bez throttlingu DRF).
    """

    def post(self, request):
        ip = request.META.get("REMOTE_ADDR", "?")
        key = f"dcr-rate:{ip}"
        licznik = cache.get(key, 0)
        if licznik >= 20:  # 20 rejestracji / okno
            return JsonResponse({"error": "rate_limited"}, status=429)
        cache.set(key, licznik + 1, timeout=3600)  # okno 1h

        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_client_metadata"}, status=400)

        redirect_uris = payload.get("redirect_uris") or []
        if not redirect_uris or not all(_dozwolony(u) for u in redirect_uris):
            return JsonResponse({"error": "invalid_redirect_uri"}, status=400)

        Application = get_application_model()
        app = Application.objects.create(
            name=(payload.get("client_name") or "mcp-client")[:255],
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=" ".join(redirect_uris),
        )
        return JsonResponse(
            {
                "client_id": app.client_id,
                "redirect_uris": redirect_uris,
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
            status=201,
        )
