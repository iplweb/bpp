from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from .models import SiteCountdown


class CountdownBlockingMiddleware(MiddlewareMixin):
    """
    Middleware blokujące dostęp do serwisu po wygaśnięciu odliczania.
    Superużytkownicy (superuser) mają zawsze dostęp, aby mogli usunąć countdown.
    """

    def process_request(self, request):
        # Pomiń middleware dla ścieżek administracyjnych, statycznych i medialnych
        if (
            request.path.startswith("/admin/")
            or request.path.startswith("/static/")
            or request.path.startswith("/media/")
        ):
            return None

        # Pobierz aktualny site
        try:
            current_site = get_current_site(request)
        except Exception:
            # Jeśli nie można pobrać site, nie blokuj
            return None

        # Sprawdź, czy istnieje countdown dla tego site
        try:
            countdown = SiteCountdown.objects.get(site=current_site)
        except SiteCountdown.DoesNotExist:
            # Brak countdown - normalny dostęp
            return None

        # Sprawdź, czy countdown wygasł
        if countdown.is_expired():
            # Jeśli prace konserwacyjne się zakończyły, pozwól na dostęp
            if countdown.is_maintenance_finished():
                return None

            # Jeśli użytkownik jest superuserem, pozwól na dostęp
            if (
                hasattr(request, "user")
                and request.user.is_authenticated
                and request.user.is_superuser
            ):
                return None

            # Zablokuj dostęp dla wszystkich innych użytkowników
            return render(
                request,
                "django_countdown/blocked.html",
                {
                    "countdown": countdown,
                    "site": current_site,
                },
                status=503,  # Service Unavailable
            )

        # Countdown jeszcze nie wygasł - normalny dostęp
        return None
