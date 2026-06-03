"""Backendy logowania zarządzające hasłami zewnętrznie.

Wydzielone do osobnego modułu, żeby views / middleware / testy mogły
używać stałej bez ciągnięcia `password_policies` (lightweight auth_server
nie ma password_policies w INSTALLED_APPS).
"""

EXTERNAL_AUTH_BACKENDS = {
    "microsoft_auth.backends.MicrosoftAuthenticationBackend",
    "orcid_integration.backends.OrcidAuthenticationBackend",
    "oidc_integration.backends.BppOIDCBackend",
}
