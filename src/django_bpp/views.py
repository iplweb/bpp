import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views import View

logger = logging.getLogger(__name__)


class HTMXAwareLoginView(LoginView):
    """
    Login view that handles HTMX requests by returning HX-Redirect header
    instead of rendering the login form inline.

    When a user's session expires and they trigger an HTMX action, Django redirects
    them to the login page. Without this view, the login page HTML would be injected
    into the HTMX target element. This view detects HTMX requests and returns
    an HX-Redirect header to trigger a full page navigation to the login page,
    preserving the original URL as the 'next' parameter.
    """

    def get(self, request, *args, **kwargs):
        if request.headers.get("HX-Request"):
            # Get the URL the user was on when the HTMX request was made
            current_url = request.headers.get("HX-Current-URL", "")

            # Build login URL with next parameter (properly URL encoded)
            login_url = reverse("login_form")
            if current_url:
                login_url = f"{login_url}?{urlencode({'next': current_url})}"

            # Return HX-Redirect to trigger full page navigation
            response = HttpResponse(status=200)
            response["HX-Redirect"] = login_url
            return response

        return super().get(request, *args, **kwargs)


class MicrosoftLogoutView(View):
    """
    Custom logout view for Microsoft authentication.

    This view properly handles logout by:
    1. Clearing the Django session using logout()
    2. Redirecting to Microsoft logout endpoint with post_logout_redirect_uri
    """

    def get(self, request):
        return self._logout(request)

    def post(self, request):
        return self._logout(request)

    def _logout(self, request):
        """Perform the logout process"""
        # If user is not authenticated, redirect to post-logout URI without calling logout
        if not request.user.is_authenticated:
            post_logout_redirect_uri = self._get_post_logout_redirect_uri(request)
            logger.info(
                "User not authenticated, redirecting directly to post-logout URI"
            )
            return HttpResponseRedirect(post_logout_redirect_uri)

        # Clear Django session first
        logout(request)
        logger.info("User session cleared from Django")

        # Build the Microsoft logout URL with redirect
        logout_url = "https://login.microsoftonline.com/common/oauth2/v2.0/logout"

        # Determine the post-logout redirect URI
        post_logout_redirect_uri = self._get_post_logout_redirect_uri(request)

        # Build the full logout URL with parameters
        params = {"post_logout_redirect_uri": post_logout_redirect_uri}

        full_logout_url = f"{logout_url}?{urlencode(params)}"

        logger.info(f"Redirecting to Microsoft logout: {full_logout_url}")

        return HttpResponseRedirect(full_logout_url)

    def _get_post_logout_redirect_uri(self, request):
        """
        Get the URI to redirect to after Microsoft logout.

        Priority:
        1. MICROSOFT_AUTH_LOGOUT_REDIRECT_URL setting
        2. LOGIN_REDIRECT_URL setting
        3. Home page ('/')
        """
        if hasattr(settings, "MICROSOFT_AUTH_LOGOUT_REDIRECT_URL"):
            redirect_path = settings.MICROSOFT_AUTH_LOGOUT_REDIRECT_URL
        elif hasattr(settings, "LOGIN_REDIRECT_URL"):
            redirect_path = settings.LOGIN_REDIRECT_URL
        else:
            redirect_path = "/"

        # Build absolute URI
        return request.build_absolute_uri(redirect_path)


@login_required
def is_superuser(request):
    """Authorization endpoint for superusers.

    Returns 200 OK with user headers if user is superuser,
    returns 403 Forbidden otherwise.
    """
    u = request.user

    if not u.is_superuser:
        return HttpResponse("forbidden", status=403)

    resp = HttpResponse("ok")
    resp["X-WEBAUTH-USER"] = u.get_username()
    resp["X-WEBAUTH-EMAIL"] = u.email or ""
    resp["X-WEBAUTH-NAME"] = u.get_full_name() or u.get_username()
    return resp
