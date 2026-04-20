from django.contrib.auth import BACKEND_SESSION_KEY
from password_policies.middleware import PasswordChangeMiddleware

from django_bpp.external_auth import EXTERNAL_AUTH_BACKENDS


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
