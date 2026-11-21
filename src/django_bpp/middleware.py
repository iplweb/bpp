from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, REDIRECT_FIELD_NAME
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.http import url_has_allowed_host_and_scheme
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


# URL names of every page that starts a login flow. Not every one exists in
# every configuration (Microsoft / OIDC are optional, auth_server has its own
# LOGIN_URL), so missing names are skipped.
LOGIN_URL_NAMES = (
    "admin:login",
    "login_form",
    "local_login_form",
    "microsoft_auth:to-auth-redirect",
    "oidc_authentication_init",
)

REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def login_paths():
    """Paths of all login pages known in the current URLconf."""
    paths = {urlsplit(resolve_url(settings.LOGIN_URL)).path}
    for name in LOGIN_URL_NAMES:
        try:
            paths.add(reverse(name))
        except NoReverseMatch:
            continue  # this login flow is not enabled in this configuration
    return paths


class HtmxLoginRedirectMiddleware(MiddlewareMixin):
    """Turn "go to the login page" into a full-page navigation for HTMX.

    When the session is gone (expiry, server restart) an HTMX request for a
    protected fragment gets a 302 to the login page. HTMX follows it
    transparently and swaps the *login form* into the target element (e.g.
    the admin filter panel). For HTMX requests of anonymous users this
    middleware replaces such responses with an empty 200 carrying
    ``HX-Redirect``, so the browser navigates to the login page and comes
    back (``?next=``) to the page the user was looking at
    (``HX-Current-URL``), not to the fragment URL.

    Handled: redirects to any known login page (``login_required``,
    ``LoginRequiredMixin``, ``redirect_to_login``, admin ``admin_view``,
    Microsoft / OIDC entry points), 401/403 responses for anonymous users and
    an HTMX GET of a login page itself.
    """

    def process_request(self, request):
        if (
            request.method == "GET"
            and self._applies(request)
            and request.path in login_paths()
        ):
            return self._hx_redirect(request, request.get_full_path())
        return None

    def process_response(self, request, response):
        if not self._applies(request) or response.has_header("HX-Redirect"):
            return response

        if response.status_code in REDIRECT_STATUSES:
            location = response.get("Location", "")
            if urlsplit(location).path in login_paths():
                return self._hx_redirect(request, location)
            return response

        if response.status_code in (401, 403):
            # Views with ``raise_exception = True`` answer anonymous users with
            # 403 instead of a login redirect; the login page is the cure.
            try:
                admin_index = reverse("admin:index")
            except NoReverseMatch:
                admin_index = None  # URLconf without the admin (auth server)
            if admin_index and request.path.startswith(admin_index):
                return self._hx_redirect(request, reverse("admin:login"))
            return self._hx_redirect(request, resolve_url(settings.LOGIN_URL))

        return response

    @staticmethod
    def _applies(request):
        if request.headers.get("HX-Request") != "true":
            return False
        user = getattr(request, "user", None)
        return user is not None and not user.is_authenticated

    def _hx_redirect(self, request, login_url):
        current_path = self._current_path(request)
        if urlsplit(current_path).path in login_paths():
            # The page in the browser already is a login page: navigating to
            # it again would only reload it (in a loop, if it polls). Just do
            # not swap anything.
            return HttpResponse(status=204)

        parts = urlsplit(login_url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != REDIRECT_FIELD_NAME
        ]
        query.append((REDIRECT_FIELD_NAME, current_path))
        response = HttpResponse(status=200)
        response["HX-Redirect"] = urlunsplit(parts._replace(query=urlencode(query)))
        return response

    @staticmethod
    def _current_path(request):
        """Path + query of the page the user is looking at.

        Taken from ``HX-Current-URL`` when it points to this site; otherwise
        (missing or foreign header) the HTMX request's own path is used.
        """
        current_url = request.headers.get("HX-Current-URL", "")
        allowed_hosts = {request.get_host()}
        if current_url and url_has_allowed_host_and_scheme(
            current_url, allowed_hosts=allowed_hosts
        ):
            parts = urlsplit(current_url)
            path = urlunsplit(("", "", parts.path or "/", parts.query, ""))
            if url_has_allowed_host_and_scheme(path, allowed_hosts=allowed_hosts):
                return path
        return request.get_full_path()
