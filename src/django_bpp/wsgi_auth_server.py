"""WSGI config for lightweight auth server.

Exposes the WSGI callable as a module-level variable named ``application``.
Uses minimal auth_server settings for fast startup.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.auth_server")

application = get_wsgi_application()
