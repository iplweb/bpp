from django.contrib.messages import constants
from django.utils.functional import cached_property

from notifications import core as notifications_core
from notifications.models import Notification


class NullNotificationMixin:
    def send_notification(self, msg, level=None):
        return

    def send_processing_finished(self):
        return


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

    def send_processing_finished(self):
        # Zamiast wysyłać redirect, który może nie zostać odebrany przez klienta
        # (np. przetwarzanie skończyło się nim strona WWW została wyświetlona)
        # utwórzmy prawdziwy obiekt notyfikacji, którego odbiór wymaga potwierdzenia
        # przez zdalną przeglądarkę.
        for elem in [
            Notification.objects.create(
                channel_name=self.asgi_channel_name,
                values=dict(progress=True, percent="100%"),
            ),
            Notification.objects.create(
                channel_name=self.asgi_channel_name, values=dict(url="..")
            ),
        ]:
            elem.send()
