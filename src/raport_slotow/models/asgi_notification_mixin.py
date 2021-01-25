from django.contrib.messages import constants
from django.utils.functional import cached_property

from notifications import core as notifications_core


class ASGINotificationMixin:
    @cached_property
    def asgi_channel_name(self):
        return str(self.pk)

    def send_notification(self, msg, level=constants.INFO):
        notifications_core.send_notification(self.asgi_channel_name, level, msg)

    def send_progress(self, percent):
        notifications_core._send(
            self.asgi_channel_name, dict(progress=True, percent=str(percent) + "%")
        )
