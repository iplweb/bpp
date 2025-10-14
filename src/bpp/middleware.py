import json

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rollbar.contrib.django.middleware import RollbarNotifierMiddleware


class NonHtmlDebugToolbarMiddleware(MiddlewareMixin):
    """
    The Django Debug Toolbar usually only works for views that return HTML.
    This middleware wraps any non-HTML response in HTML if the request
    has a 'debug' query parameter (e.g. http://localhost/foo?debug)
    Special handling for json (pretty printing) and
    binary data (only show data length)
    """

    @staticmethod
    def process_response(request, response):
        debug = request.GET.get("debug", "UNSET")

        if debug != "UNSET":
            if response["Content-Type"] == "application/octet-stream":
                new_content = (
                    "<html><body>Binary Data, "
                    f"Length: {len(response.content)}</body></html>"
                )
                response = HttpResponse(new_content)
            elif response["Content-Type"] != "text/html":
                content = response.content
                try:
                    json_ = json.loads(content)
                    content = json.dumps(json_, sort_keys=True, indent=2)
                except ValueError:
                    pass
                response = HttpResponse(
                    f"<html><body><pre>{content}" "</pre></body></html>"
                )

        return response


class CustomRollbarNotifierMiddleware(RollbarNotifierMiddleware):
    def get_extra_data(self, request, exc):
        from django.conf import settings

        return {
            "DJANGO_BPP_HOSTNAME": settings.DJANGO_BPP_HOSTNAME,
        }

    def get_payload_data(self, request, exc):
        payload_data = dict()

        if not request.user.is_anonymous:
            # Adding info about the user affected by this event (optional)
            # The 'id' field is required, anything else is optional
            payload_data = {
                "person": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                },
            }

        return payload_data
