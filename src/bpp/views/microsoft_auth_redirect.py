import logging

from django.core.signing import dumps
from django.http import HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.views import View

logger = logging.getLogger(__name__)


class MicrosoftAuthRedirectView(View):
    """
    View that generates Microsoft authentication redirect URL.

    This view replaces the direct usage of microsoft_auth context processor
    to avoid making network requests on every page load. It generates the
    Microsoft OAuth2 authorization URL only when actually needed.
    """

    def get(self, request):
        """
        Generate Microsoft auth URL and return as JSON or redirect.

        Query parameters:
        - format: 'json' to return URL as JSON, otherwise redirect directly
        - next: URL to redirect to after successful authentication
        """
        try:
            # Import here to avoid import errors if microsoft_auth is not installed
            from microsoft_auth.client import MicrosoftClient
            from microsoft_auth.conf import config

            if not config.MICROSOFT_AUTH_LOGIN_ENABLED:
                return JsonResponse(
                    {"error": "Microsoft authentication is not enabled"}, status=400
                )

            # Initialize state with CSRF token and optional next path
            state = {"token": get_token(request)}
            next_url = request.GET.get("next")
            if next_url:
                state["next"] = next_url

            # Sign the state for security
            signed_state = dumps(state, salt="microsoft_auth")

            # Create Microsoft client and get authorization URL
            microsoft = MicrosoftClient(state=signed_state, request=request)
            auth_url = microsoft.authorization_url()[0]

            # Return format based on request
            if request.GET.get("format") == "json":
                return JsonResponse({"auth_url": auth_url, "success": True})
            else:
                # Direct redirect to Microsoft
                return HttpResponseRedirect(auth_url)

        except ImportError:
            logger.error("microsoft_auth package is not installed")
            return JsonResponse(
                {"error": "Microsoft authentication is not configured"}, status=500
            )
        except Exception as e:
            logger.error(f"Error generating Microsoft auth URL: {str(e)}")
            return JsonResponse(
                {"error": "Failed to generate authentication URL"}, status=500
            )
