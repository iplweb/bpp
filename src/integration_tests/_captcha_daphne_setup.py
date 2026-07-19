"""Callback ``setup`` dla ``DaphneProcess`` używany przez
``test_zglos_captcha_gating.py`` — wymusza ``ZGLOS_CAPTCHA_ENABLED=True`` w
subprocesie Daphne.

Osobny, "lekki" moduł CELOWO (mirror ``channels_live_server.py``): na
macOS ``multiprocessing`` uruchamia dziecko metodą "spawn" — świeży
interpreter, który pickluje callback ``setup`` PO NAZWIE KWALIFIKOWANEJ i
odtwarza go importując cały jego moduł, ZANIM ``django.setup()``/
``apps.populate()`` zdąży się wykonać w dziecku. Gdyby ta funkcja siedziała
w ``test_zglos_captcha_gating.py`` (top-level ``from model_bakery import
baker`` / ``from bpp.models import Uczelnia``), import tamtego modułu w
dziecku wywaliłby się ``AppRegistryNotReady`` (empirycznie potwierdzone —
patrz docstring modułu testowego). Ten moduł, jak ``channels_live_server.py``,
nie importuje niczego Django-owego na poziomie modułu — tylko wewnątrz
funkcji, gdy apps są już gotowe.
"""

# Stały klucz testowy (64 znaki hex) — captcha ON tylko dla testów w
# test_zglos_captcha_gating.py. Re-eksportowany stamtąd jako `_TEST_KEY`.
TEST_ALTCHA_HMAC_KEY = "0" * 64


def setup_captcha_daphne():
    """Wykonywane W SUBPROCESIE Daphne, przed ``self.server.run()``.

    Widok czyta ``settings.ZGLOS_CAPTCHA_ENABLED``/``ALTCHA_HMAC_KEY``
    "call-time" (per request — patrz ``zglos_publikacje/views.py``
    ``get_form_kwargs``), więc mutacja tutaj, przed startem serwera,
    wystarcza na czas życia całego subprocesu.
    """
    from channels_live_server import set_database_connection

    set_database_connection()

    from django.conf import settings

    settings.ZGLOS_CAPTCHA_ENABLED = True
    settings.ALTCHA_HMAC_KEY = TEST_ALTCHA_HMAC_KEY
