"""Backendy logowania zarządzające hasłami zewnętrznie.

Wydzielone do osobnego modułu, żeby views / middleware / testy mogły
używać stałej bez ciągnięcia `password_policies` (lightweight auth_server
nie ma password_policies w INSTALLED_APPS).
"""

MICROSOFT_BACKEND = "microsoft_auth.backends.MicrosoftAuthenticationBackend"
ORCID_BACKEND = "orcid_integration.backends.OrcidAuthenticationBackend"
OIDC_BACKEND = "oidc_integration.backends.BppOIDCBackend"

EXTERNAL_AUTH_BACKENDS = {
    MICROSOFT_BACKEND,
    ORCID_BACKEND,
    OIDC_BACKEND,
}
