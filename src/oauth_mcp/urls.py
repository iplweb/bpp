from django.urls import include, path
from oauth2_provider import urls as oauth2_urls

# BEZ `app_name` na tym module! Deklaracja `app_name="oauth_mcp"` zagnieżdżałaby
# namespace DOT (`oauth_mcp:oauth2_provider:authorize`) i psuła
# `{% url 'oauth2_provider:authorize' %}` w szablonie zgody → NoReverseMatch.
# Zostawiamy `oauth2_provider:*` na top-levelu, jak w dokumentacji DOT.

# UWAGA: montujemy TYLKO base_urlpatterns (authorize/token/introspect/revoke),
# NIE management-views (/o/applications/ CRUD dostępne każdemu zalogowanemu).
urlpatterns = [
    path("o/", include((oauth2_urls.base_urlpatterns, "oauth2_provider"))),
]
