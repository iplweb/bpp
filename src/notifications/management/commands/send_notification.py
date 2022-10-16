import messages_extends as messages
from django.core.management import BaseCommand

from notifications.core import get_channel_name_for_user, send_notification

from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Wysyla notyfikacje realtime via django-channels"
    args = "<username> <message>"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("text")

    def handle(self, *args, **options):
        user = get_user_model().objects.get(username=options["username"])
        channel_name = get_channel_name_for_user(user)

        send_notification(
            channel_name,
            messages.INFO_PERSISTENT,
            options["text"],
        )
