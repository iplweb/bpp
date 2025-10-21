"""
Mixins for autocomplete views.
"""


class SanitizedAutocompleteMixin:
    """
    Mixin to sanitize autocomplete input by truncating excessively long queries.

    This prevents recursion issues and performance problems caused by malicious
    or accidentally pasted long input strings in autocomplete fields.

    Maximum query length is set to 120 characters.
    """

    MAX_QUERY_LENGTH = 120

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to truncate query parameter before processing."""
        # Truncate the query parameter in the request BEFORE parent processes it
        q = request.GET.get("q", "")
        if q and len(q) > self.MAX_QUERY_LENGTH:
            # Create a mutable copy of request.GET
            request.GET = request.GET.copy()
            request.GET["q"] = q[: self.MAX_QUERY_LENGTH]

        return super().dispatch(request, *args, **kwargs)
