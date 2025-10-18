import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.views import View

logger = logging.getLogger(__name__)


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
