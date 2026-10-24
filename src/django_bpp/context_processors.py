from django.contrib.auth import BACKEND_SESSION_KEY

from django_bpp.external_auth import EXTERNAL_AUTH_BACKENDS


def conditional_password_status(request):
    """Wariant `password_policies.context_processors.password_status`,
    który pomija sprawdzanie wieku hasła dla użytkowników zalogowanych
    przez backendy OAuth (Microsoft, ORCID).

    Symetryczny do `ConditionalPasswordChangeMiddleware`: bez tego
    middleware słusznie nie redirectuje użytkownika OAuth do widoku
    zmiany hasła, ale oryginalny context processor i tak ustawia
    `password_change_required = True` (po fallbacku do
    `PasswordHistory.objects.change_required`), więc `base.html`
    pokazuje callout o przeterminowanym haśle bez formularza
    zmiany — zmienna `form` jest dostępna tylko w widoku zmiany hasła.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}

    backend = request.session.get(BACKEND_SESSION_KEY, "")
    if backend in EXTERNAL_AUTH_BACKENDS:
        return {"password_change_required": False}

    from password_policies.conf import settings as password_settings
    from password_policies.context_processors import password_status
    from password_policies.models import PasswordChangeRequired

    # Rotacja wyłączona (0): liczy się tylko ręczne wymuszenie zmiany
    # (PasswordChangeRequired), które biblioteka przy zerowym duration
    # pomija -- symetrycznie do ConditionalPasswordChangeMiddleware.
    if not password_settings.PASSWORD_DURATION_SECONDS:
        required = request.session.get(
            password_settings.PASSWORD_POLICIES_CHANGE_REQUIRED_SESSION_KEY
        )
        if required is None:
            required = PasswordChangeRequired.objects.filter(user=request.user).exists()
        return {"password_change_required": required}

    return password_status(request)
