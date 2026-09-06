from django.http import JsonResponse


def oauth_authorization_server_metadata(request):
    """RFC 8414 — DOT nie shipuje czystego wariantu, piszemy sami (spec §5.6).

    Issuer = ROOT hosta (bez /o); URL-e przez build_absolute_uri (poprawny
    scheme z SECURE_PROXY_SSL_HEADER, host per-request — wielo-domenowość).
    """
    issuer = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "issuer": issuer,
            "authorization_endpoint": request.build_absolute_uri("/o/authorize/"),
            "token_endpoint": request.build_absolute_uri("/o/token/"),
            "revocation_endpoint": request.build_absolute_uri("/o/revoke_token/"),
            "registration_endpoint": request.build_absolute_uri("/o/register/"),
            "scopes_supported": ["read"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


def oauth_protected_resource_metadata(request):
    """RFC 9728 — mówi klientowi MCP, który serwer autoryzacji obsługuje /mcp.

    Poprzedni spec przypisywał ten dokument pakietowi bpp-mcp; odkąd Resource
    Serverem jest sama instancja BPP, mieszka on tutaj. URL-e przez
    build_absolute_uri — poprawny scheme z SECURE_PROXY_SSL_HEADER, host
    per-request (wielo-domenowość).
    """
    return JsonResponse(
        {
            "resource": request.build_absolute_uri("/mcp"),
            "authorization_servers": [request.build_absolute_uri("/").rstrip("/")],
            "scopes_supported": ["read"],
            "bearer_methods_supported": ["header"],
        }
    )
