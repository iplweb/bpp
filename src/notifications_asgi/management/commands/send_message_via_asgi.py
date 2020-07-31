# -*- encoding: utf-8 -*
from optparse import make_option

import channels
from asgiref.sync import async_to_sync

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.db import transaction

import messages_extends as messages
from django.contrib.auth import get_user_model

from django.core.management import BaseCommand
from django.test import RequestFactory
from messages_extends.storages import PersistentStorage

import notifications
from messages_extends.models import Message


class Command(BaseCommand):
    help = "Wysyla komunikat offline za pomoca frameworku messages"
    args = "<username> <message>"

    def add_arguments(self, parser):
        parser.add_argument("channel_name")
        parser.add_argument("text")

        # parser.add_argument('--dont-persist',
        #             action='store_true',
        #             dest='no_persist',
        #             default=False,
        #             help="Don't persist the message")

    def handle(self, channel_name, text, *args, **options):
        # request_factory = RequestFactory()
        #
        # request = request_factory.get('/')
        #
        # request.user = get_user_model().objects.get(
        #     username=options['username'])
        # setattr(request, 'session', 'session')
        #
        # storage = PersistentStorage(request)
        #
        # setattr(request, '_messages', storage)
        #
        # level = messages.INFO_PERSISTENT
        # text = options['text']
        #
        # msg = None

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()

        fun = channel_layer.group_send
        if channel_name.startswith("specific"):
            fun = channel_layer.send

        ret = async_to_sync(fun)(
            channel_name, {"type": "chat_message", "message": text, "text_data": "!23"},
        )
        print(ret)

        #
        # notifications.send_notification(
        #     request,
        #     level,
        #     text,
        #     verbose=int(options["verbosity"]) > 1,
        #     ignore_proxy_settings=options["ignore_proxy"],
        # )
        # return
        #
        # with transaction.atomic():
        #     messages.add_message(request, level, text)
        #     msg = Message.objects.filter(user_id=request.user.pk, message=text).order_by('-pk')[:1]
        #
        # if msg:
        #     msg = msg[0]
        #     closeURL = reverse('messages_extends:message_mark_read', args=(msg.pk,))
        #     notifications.send_notification(
        #         request, level, text, verbose=int(options['verbosity']) > 1, closeURL=closeURL, ignore_proxy_settings=options['ignore_proxy'])
