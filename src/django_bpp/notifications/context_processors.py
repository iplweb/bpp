from notifications.conf import settings

def notification_settings(request):
    return dict(
        NOTIFICATIONS_HOST=getattr(settings, "NOTIFICATIONS_HOST"),
        NOTIFICATIONS_PORT=getattr(settings, "NOTIFICATIONS_PORT"),
        NOTIFICATIONS_PROTOCOL=getattr(settings, "NOTIFICATIONS_PROTOCOL"),
        NOTIFICATIONS_PUB_PREFIX=getattr(settings, "NOTIFICATIONS_PUB_PREFIX"),
        NOTIFICATIONS_PUB_PATH=getattr(settings, "NOTIFICATIONS_PUB_PATH"),

    )
