"""Views for previewing error pages (403, 500) and triggering test
exceptions for Rollbar verification.
"""

from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse


def test_403_view(request):
    """Trigger 403 Forbidden error page."""
    raise PermissionDenied("Test 403 error page")


def test_exception_view(request):
    """Trigger an uncaught exception to verify Rollbar reporting."""
    raise Exception("Celowe wywołanie błedu. ")


def test_500_view(request):
    """Serve the static 500.html page for preview."""
    static_500_path = Path(__file__).parent.parent / "static" / "500.html"
    if static_500_path.exists():
        content = static_500_path.read_text(encoding="utf-8")
        return HttpResponse(content, content_type="text/html")
    return HttpResponse(
        f"500.html not found at {static_500_path}. "
        f"Run 'python src/manage.py generate_500_page' to generate it.",
        status=404,
    )
