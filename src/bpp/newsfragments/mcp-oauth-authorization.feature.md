Warstwa autoryzacji OAuth 2.1 dla serwera MCP: BPP działa jako Authorization
Server (`django-oauth-toolkit`) z endpointami `/o/authorize`, `/o/token`,
`/o/revoke_token`, własnym Dynamic Client Registration `/o/register/` (RFC 7591)
i metadanymi `/.well-known/oauth-authorization-server` (RFC 8414). API `/api/v1/`
przyjmuje token `Bearer` z uprawnieniami zalogowanego użytkownika (odczyt),
udostępnia endpoint `/api/v1/whoami/` do weryfikacji tożsamości i jest twardo
read-only dla tokenów. Logowanie w kroku zgody korzysta ze wszystkich metod BPP
(hasło/LDAP/Microsoft/ORCID/Keycloak). Tokeny są krótkotrwałe, z rotacją refresh
i unieważnieniem przy zmianie hasła lub dezaktywacji konta.
