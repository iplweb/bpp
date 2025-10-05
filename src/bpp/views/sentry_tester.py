from django.core.exceptions import PermissionDenied


def sentry_teset_view(request, *args, **kw):
    raise Exception("Planowe wywołanie procedury testującej obsługę wyjątków")


def test_403_view(request):
    """Test view to trigger 403 Forbidden error page."""
    raise PermissionDenied("Test 403 error page")


def test_500_view(request):
    """Test view to trigger 500 Internal Server Error page."""
    raise Exception("Test 500 error page")
