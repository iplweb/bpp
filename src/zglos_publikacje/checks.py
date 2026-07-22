"""System-check ostrzegający, że CAPTCHA jest włączona z kluczem-placeholderem.

Świadomie **nie-fatalny** (Warning, nie Error) — nie wywala `collectstatic`
ani buildu (mirror wzorca `SECRET_KEY`, który też nie fail-fastuje). Realną
gwarancję realnego klucza w produkcji daje auto-gen w bpp-deploy; ten check to
best-effort sygnał dla operatora (widoczny przy `manage.py check`/`migrate`).
"""

from django.conf import settings
from django.core import checks

W001_ID = "zglos_publikacje.W001"


def _klucz_wyglada_na_placeholder(klucz: str) -> bool:
    if not klucz:
        return True
    if klucz == getattr(settings, "ALTCHA_HMAC_KEY_UNSET", None):
        return True
    # .env.docker placeholder ("ZMIEN...") oraz build-time dummy.
    return "ZMIEN" in klucz or "build-time" in klucz


@checks.register()
def captcha_key_placeholder_check(app_configs, **kwargs):
    if not getattr(settings, "ZGLOS_CAPTCHA_ENABLED", False):
        return []
    if _klucz_wyglada_na_placeholder(getattr(settings, "ALTCHA_HMAC_KEY", "")):
        return [
            checks.Warning(
                "ZGLOS_CAPTCHA_ENABLED jest włączone, ale ALTCHA_HMAC_KEY "
                "wygląda na placeholder — CAPTCHA będzie możliwa do podrobienia "
                "(HMAC znany). Ustaw realny klucz (auto-gen w bpp-deploy).",
                hint="Wygeneruj: openssl rand -hex 32; wstrzyknij jako env "
                "ALTCHA_HMAC_KEY do serwisów Django.",
                id=W001_ID,
            )
        ]
    return []
