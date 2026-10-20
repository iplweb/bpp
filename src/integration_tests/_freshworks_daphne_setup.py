"""Callback ``setup`` dla ``DaphneProcess`` używany przez
``test_admin_freshworks_lazy.py`` — wymusza ``TESTING=False`` w subprocesie
Daphne, żeby ``admin/base_site.html`` wyrenderował widget wsparcia
Freshworks (szablon chowa go za ``{% if not TESTING %}``).

Osobny, lekki moduł CELOWO — z tego samego powodu co
``_captcha_daphne_setup.py``: na macOS ``multiprocessing`` startuje dziecko
metodą "spawn" i importuje moduł callbacku zanim ``django.setup()`` się
wykona, więc nie wolno tu importować niczego Django-owego na poziomie modułu.
"""


def setup_freshworks_daphne():
    """Wykonywane W SUBPROCESIE Daphne, przed ``self.server.run()``.

    Context processor ``bpp.context_processors.testing`` czyta
    ``settings.TESTING`` per request, więc mutacja tutaj wystarcza.
    """
    from channels_live_server import set_database_connection

    set_database_connection()

    from django.conf import settings

    settings.TESTING = False


#: Sekret JWT widgetu dla ``setup_freshworks_daphne_jwt`` (tylko testy).
JWT_SECRET = "sekret-widgetu-freshdesk-do-testow-playwright-0123456789"


def setup_freshworks_daphne_jwt():
    """Jak ``setup_freshworks_daphne``, plus włączone uwierzytelnianie JWT."""
    setup_freshworks_daphne()

    from django.conf import settings

    settings.FRESHDESK_WIDGET_JWT_SECRET = JWT_SECRET


#: ID widgetu dla anonimów w ``setup_freshworks_daphne_anon`` (tylko testy).
WIDGET_ID_ANON = "205000000999"


def setup_freshworks_daphne_anon():
    """Jak ``setup_freshworks_daphne``, plus widget dla niezalogowanych."""
    setup_freshworks_daphne()

    from django.conf import settings

    settings.FRESHDESK_WIDGET_ID_ANON = WIDGET_ID_ANON
