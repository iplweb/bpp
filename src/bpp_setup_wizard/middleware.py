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

    def process_request(self, request):
        # Skip middleware for static files and media files
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return None

        # Skip if we're already on the setup wizard URLs
        if request.path.startswith("/setup/"):
            return None

        # Skip for admin URLs during setup (in case we need to access admin for debugging)
        if request.path.startswith("/admin/") and request.path != "/admin/":
            # Allow access to admin if users exist
            try:
                if BppUser.objects.exists():
                    return None
            except BaseException:
                # Database might not be migrated yet
                return None

        # Skip for migration-related URLs
        if any(path in request.path for path in ["migrate", "__debug__"]):
            return None

        # Skip for login/logout URLs
        if any(path in request.path for path in ["login", "logout", "accounts"]):
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
