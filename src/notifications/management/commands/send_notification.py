# -*- encoding: utf-8 -*

import messages_extends as messages
from django.contrib.auth import get_user_model

from django.core.management import BaseCommand
from django.test import RequestFactory
from messages_extends.storages import PersistentStorage

import notifications
from notifications.core import _send, send_notification


class Command(BaseCommand):
    help = "Wysyla notyfikacje realtime via django-channels"
    args = "<username> <message>"

    def add_arguments(self, parser):
        parser.add_argument("user")
        parser.add_argument("text")

    def handle(self, *args, **options):
        send_notification(
            options["user"], messages.INFO_PERSISTENT, options["text"],
        )
