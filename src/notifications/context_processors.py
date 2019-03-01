from django.conf import settings
from notifications.conf import defaults

def notification_settings(request):
    return dict(
        NOTIFICATIONS_HOST=getattr(settings, "NOTIFICATIONS_HOST", defaults.NOTIFICATIONS_HOST),
        NOTIFICATIONS_PORT=getattr(settings, "NOTIFICATIONS_PORT", defaults.NOTIFICATIONS_PORT),
        NOTIFICATIONS_PROTOCOL=getattr(settings, "NOTIFICATIONS_PROTOCOL", defaults.NOTIFICATIONS_PROTOCOL),
        NOTIFICATIONS_PUB_PREFIX=getattr(settings, "NOTIFICATIONS_PUB_PREFIX", defaults.NOTIFICATIONS_PUB_PREFIX),
        NOTIFICATIONS_PUB_PATH=getattr(settings, "NOTIFICATIONS_PUB_PATH", defaults.NOTIFICATIONS_PUB_PATH),

    )
