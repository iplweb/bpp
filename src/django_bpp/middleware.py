from django.contrib.auth import BACKEND_SESSION_KEY
from django.urls import Resolver404, resolve, reverse
from django.utils.deprecation import MiddlewareMixin
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


# Headers that tell the front web server (nginx / Apache mod_xsendfile) to serve
# the file itself. The application response then carries no body.
OFFLOAD_HEADERS = ("X-Accel-Redirect", "X-Sendfile")


class OffloadedFileContentLengthMiddleware(MiddlewareMixin):
    """Keep ``Content-Length`` consistent with the body of offloaded responses.

    ``django_sendfile.sendfile`` sets ``Content-Length`` to the size of the
    file on disk regardless of the backend. With the ``nginx`` (or
    ``xsendfile``) backend the body is empty, because the web server serves the
    file after seeing ``X-Accel-Redirect``. WSGI servers tolerated the mismatch,
    but under ASGI uvicorn raises ``RuntimeError: Response content shorter than
    Content-Length`` for every such response (``/favicon.ico``, protected
    downloads), logging "Exception in ASGI application".

    nginx ignores the upstream ``Content-Length`` on an internal redirect and
    uses the size of the served file, so declaring the real (empty) body length
    is safe for clients.
    """

    def process_response(self, request, response):
        if response.streaming or not any(
            response.has_header(header) for header in OFFLOAD_HEADERS
        ):
            return response
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
