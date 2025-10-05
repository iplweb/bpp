from django.core.exceptions import PermissionDenied


def sentry_teset_view(request, *args, **kw):
    raise Exception("Planowe wywołanie procedury testującej obsługę wyjątków")


def test_403_view(request):
    """Test view to trigger 403 Forbidden error page."""
    raise PermissionDenied("Test 403 error page")


def test_500_view(request):
    """Test view to serve the static 500.html page for preview."""
    from pathlib import Path

    from django.http import HttpResponse

    # Load the generated static 500.html file
    static_500_path = Path(__file__).parent.parent / "static" / "500.html"
    if static_500_path.exists():
        content = static_500_path.read_text(encoding="utf-8")
        return HttpResponse(content, content_type="text/html")
    else:
        return HttpResponse(
            f"500.html not found at {static_500_path}. "
            f"Run 'python src/manage.py generate_500_page' to generate it.",
            status=404,
        )
