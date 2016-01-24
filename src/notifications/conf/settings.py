from django.conf import settings

NOTIFICATIONS_HOST = getattr(settings, "NOTIFICATIONS_HOST", '127.0.0.1')
NOTIFICATIONS_PORT = getattr(settings, "NOTIFICATIONS_PORT", 80)
NOTIFICATIONS_PROTOCOL = getattr(settings, "NOTIFICATIONS_PROTOCOL", 'http')

NOTIFICATIONS_PUB_PREFIX = getattr(settings, "NOTIFICATIONS_PUB_PREFIX", 'my-django-app')
NOTIFICATIONS_PUB_PATH = getattr(settings, "NOTIFICATIONS_PUB_PATH", '/pub/?id=%(prefix)s-%(username)s')

# NOTIFICATIONS_ADMIN_USERNAME = 'admin'
# NOTIFICATIONS_ADMIN_PASSWORD = 'admin'
