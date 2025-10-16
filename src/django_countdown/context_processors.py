from django.contrib.sites.shortcuts import get_current_site

from .models import SiteCountdown


def countdown_context(request):
    """
    Context processor dodający aktywne odliczanie do kontekstu szablonów.
    Zwraca countdown tylko jeśli istnieje i nie wygasł.
    Dla superuserów zwraca również countdown w trakcie konserwacji.
    """
    try:
        current_site = get_current_site(request)
        countdown = SiteCountdown.objects.get(site=current_site)

        # Zwróć countdown tylko jeśli nie wygasł
        if not countdown.is_expired():
            return {"active_countdown": countdown, "maintenance_countdown": None}

        # Jeśli countdown wygasł ale trwa konserwacja i użytkownik to superuser
        if countdown.is_expired() and not countdown.is_maintenance_finished():
            if (
                hasattr(request, "user")
                and request.user.is_authenticated
                and request.user.is_superuser
            ):
                return {"active_countdown": None, "maintenance_countdown": countdown}
    except (SiteCountdown.DoesNotExist, Exception):
        pass

    return {"active_countdown": None, "maintenance_countdown": None}
