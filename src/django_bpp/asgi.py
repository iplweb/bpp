import os

from channels.routing import get_default_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings")
import django

django.setup()
application = get_default_application()
