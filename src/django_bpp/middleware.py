from django.contrib.auth import BACKEND_SESSION_KEY
from password_policies.middleware import PasswordChangeMiddleware

# Backendy zarządzające hasłami zewnętrznie -- nie wymuszamy
# zmiany hasła dla użytkowników zalogowanych tymi backendami.
EXTERNAL_AUTH_BACKENDS = {
    "microsoft_auth.backends.MicrosoftAuthenticationBackend",
    "orcid_integration.backends.OrcidAuthenticationBackend",
}


class ConditionalPasswordChangeMiddleware(PasswordChangeMiddleware):
    """Pomija egzekwowanie polityki haseł dla użytkowników
    zalogowanych przez backendy OAuth (Microsoft, ORCID)."""

    def process_request(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        backend = request.session.get(BACKEND_SESSION_KEY, "")
        if backend in EXTERNAL_AUTH_BACKENDS:
            return None

        return super().process_request(request)
