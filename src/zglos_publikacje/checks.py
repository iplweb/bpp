"""System-check ostrzegający, że CAPTCHA jest włączona z kluczem-placeholderem.

Świadomie **nie-fatalny** (Warning, nie Error) — sygnał dla dev/operatora
(widoczny przy `manage.py check`/`migrate`). W ustawieniach produkcyjnych ta
sama konfiguracja jest fail-closed: `production.py` rzuca ImproperlyConfigured
(wspólny predykat w `django_bpp/settings/altcha_key_guard.py`).
"""

from django.conf import settings
from django.core import checks

from django_bpp.settings.altcha_key_guard import (
    altcha_klucz_niebezpieczny_placeholder,
)

W001_ID = "zglos_publikacje.W001"


def _klucz_wyglada_na_placeholder(klucz: str) -> bool:
    return altcha_klucz_niebezpieczny_placeholder(
        klucz, unset_sentinel=getattr(settings, "ALTCHA_HMAC_KEY_UNSET", None)
    )


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
