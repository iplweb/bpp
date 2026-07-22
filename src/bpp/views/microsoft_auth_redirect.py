import logging

from django.core.signing import dumps
from django.http import HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

logger = logging.getLogger(__name__)


def _safe_next(request, next_url):
    """Zwróć ``next_url`` tylko gdy wskazuje na TEN host (albo jest względny).

    Podpisanie stanu (``dumps(..., salt="microsoft_auth")``) dowodzi jedynie,
    że to BPP podpisało wartość — NIE że cel przekierowania jest bezpieczny.
    Bez tej walidacji ``?next=https://evil.example/`` przechodzi przez podpis,
    a callback biblioteki ``microsoft_auth`` przekierowuje tam po zalogowaniu
    (open redirect / phishing z zaufanej domeny — uwaga reviewera #2).
    """
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


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

            # Initialize state with CSRF token and optional next path.
            # `next` jest walidowane pod kątem hosta ZANIM trafi do podpisanego
            # stanu — inaczej podpis „uwiarygodnia" obcy cel (uwaga #2).
            state = {"token": get_token(request)}
            next_url = _safe_next(request, request.GET.get("next"))
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
