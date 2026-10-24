from django.contrib.auth import BACKEND_SESSION_KEY
from django.urls import Resolver404, resolve, reverse
from password_policies.conf import settings as password_settings
from password_policies.middleware import PasswordChangeMiddleware
from password_policies.models import PasswordChangeRequired

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

        if not password_settings.PASSWORD_DURATION_SECONDS:
            return self._wymus_zmiane_na_zadanie(request)

        return super().process_request(request)

    def _wymus_zmiane_na_zadanie(self, request):
        """Rotacja wyłączona: biblioteka nie sprawdza wtedy nic, ale ręczne
        wymuszenie zmiany (wpis PasswordChangeRequired, np. po podejrzeniu
        wycieku hasła) ma działać dalej. Zapis nowego hasła kasuje wpis."""
        if request.method != "GET":
            return None
        try:
            resolve(request.path_info)
        except Resolver404:
            return None
        if (
            request.user.get_username()
            in password_settings.PASSWORD_CHANGE_MIDDLEWARE_EXCLUDED_USERNAMES
        ):
            return None

        self.url = reverse("password_change")
        if self._is_excluded_path(request.path):
            return None

        request.session[self.required] = PasswordChangeRequired.objects.filter(
            user=request.user
        ).exists()
        return self._redirect(request)
