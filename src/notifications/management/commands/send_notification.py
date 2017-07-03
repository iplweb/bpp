# -*- encoding: utf-8 -*

import messages_extends as messages
from django.contrib.auth import get_user_model

from django.core.management import BaseCommand
from django.test import RequestFactory
from messages_extends.storages import PersistentStorage

import notifications


class Command(BaseCommand):
    help = 'Wysyla notyfikacje realtime via nginx-push-module'
    args = '<username> <message>'

    def add_arguments(self, parser):
        parser.add_argument("user")
        parser.add_argument("text")

    def handle(self, *args, **options):
        notifications.send_notification(options['user'],
                                        messages.INFO_PERSISTENT,
                                        options['text'],
                                        verbose=options['verbosity']>0)

