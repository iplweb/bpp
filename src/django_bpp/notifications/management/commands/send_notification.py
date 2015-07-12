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

    def handle(self, *args, **options):
        notifications.send_notification(args[0], messages.INFO_PERSISTENT, args[1], verbose=options['verbosity']>0)

