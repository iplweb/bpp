# -*- encoding: utf-8 -*-
import os
from pprint import pprint

from django.core.management import BaseCommand

from pbn_api.core import PBNClient, RequestsTransport


class Command(BaseCommand):
    help = "Odbudowuje cache"

    def add_arguments(self, parser):
        parser.add_argument("--app-id", default=os.getenv("PBN_CLIENT_APP_ID"))
        parser.add_argument("--app-token", default=os.getenv("PBN_CLIENT_APP_TOKEN"))
        parser.add_argument(
            "--base-url",
            default=os.getenv(
                "PBN_CLIENT_BASE_URL", "https://pbn-micro-alpha.opi.org.pl/api"
            ),
        )
        parser.add_argument("command", nargs="?")

    def handle(self, app_id, app_token, base_url, command=None, *args, **options):
        transport = RequestsTransport(app_id, app_token, base_url)
        client = PBNClient(transport)

        def exec(cmd):
            pprint(getattr(client, cmd)())

        if command:
            exec(command)
        else:
            while True:
                cmd = input("cmd> ")
                if cmd == "exit":
                    break
                exec(cmd)
