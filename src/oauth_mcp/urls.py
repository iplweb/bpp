from django.urls import include, path
from oauth2_provider import views as oauth2_views

from oauth_mcp.views_dcr import DynamicClientRegistrationView
from oauth_mcp.views_metadata import oauth_authorization_server_metadata

# BEZ `app_name` na tym module! Deklaracja `app_name="oauth_mcp"` zagnieżdżałaby
# namespace DOT (`oauth_mcp:oauth2_provider:authorize`) i psuła
# `{% url 'oauth2_provider:authorize' %}` w szablonie zgody → NoReverseMatch.
# Zostawiamy `oauth2_provider:*` na top-levelu, jak w dokumentacji DOT.

# Montujemy WYŁĄCZNIE authorize/token/revoke — świadomie POMIJAMY device-flow
# (RFC 8628, niechciany w MVP: nieuwierzytelniony, csrf-exempt, nielimitowany
# POST /o/device-authorization/ zapisujący DeviceGrant do bazy — wektor
# resource-exhaustion przy otwartym DCR) oraz management-views (/o/applications/
# CRUD dostępne każdemu zalogowanemu). Introspekcja odroczona (wariant whoami,
# spec §5.4c/d) — doda się przy wariancie confidential-client.
_authorization_server_urls = [
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path(
        "revoke_token/",
        oauth2_views.RevokeTokenView.as_view(),
        name="revoke-token",
    ),
]

urlpatterns = [
    path("o/", include((_authorization_server_urls, "oauth2_provider"))),
    path("o/register/", DynamicClientRegistrationView.as_view(), name="dcr"),
    path(
        ".well-known/oauth-authorization-server",
        oauth_authorization_server_metadata,
        name="oauth-as-metadata",
    ),
]
