from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from bpp.models import Uczelnia

BppUser = get_user_model()


class SetupWizardMiddleware(MiddlewareMixin):
    """
    Middleware to redirect to setup wizard when database is empty.
    Handles both user setup and uczelnia setup.
    """

    SKIP_PREFIXES = (
        "/static/",
        "/media/",
        "/metrics",
        "/setup/",
    )

    SKIP_SUBSTRINGS = (
        "migrate",
        "__debug__",
        "login",
        "logout",
        "accounts",
    )

    def _should_skip(self, request):
        path = request.path

        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return True

        if any(s in path for s in self.SKIP_SUBSTRINGS):
            return True

        if path.startswith("/admin/") and path != "/admin/":
            try:
                if BppUser.objects.exists():
                    return True
            except BaseException:
                return True

        return False

    def process_request(self, request):
        if self._should_skip(request):
            return None

        # First check if any users exist
        try:
            needs_user_setup = not BppUser.objects.exists()
        except BaseException:
            # If there's an error (e.g., table doesn't exist), don't redirect
            # This allows migrations to run properly
            return None

        if needs_user_setup:
            # Redirect to user setup wizard
            setup_url = reverse("bpp_setup_wizard:setup")
            if request.path != setup_url:
                return redirect(setup_url)

        # If users exist, check if Uczelnia is configured
        try:
            needs_uczelnia_setup = not Uczelnia.objects.exists()
        except BaseException:
            # Table might not exist yet
            return None

        if needs_uczelnia_setup:
            # Only redirect authenticated superusers to Uczelnia setup
            # Check if request has user attribute (set by AuthenticationMiddleware)
            if (
                hasattr(request, "user")
                and request.user.is_authenticated
                and request.user.is_superuser
            ):
                uczelnia_url = reverse("bpp_setup_wizard:uczelnia_setup")
                if request.path != uczelnia_url:
                    return redirect(uczelnia_url)

        return None
