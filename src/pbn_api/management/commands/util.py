from django.core.management import BaseCommand

from pbn_api.client import PBNClient, RequestsTransport
from pbn_api.conf import settings


class PBNBaseCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--app-id", default=getattr(settings, "PBN_CLIENT_APP_ID"))
        parser.add_argument(
            "--app-token", default=getattr(settings, "PBN_CLIENT_APP_TOKEN")
        )
        parser.add_argument(
            "--base-url", default=getattr(settings, "PBN_CLIENT_BASE_URL")
        )

    def get_client(self, app_id, app_token, base_url):
        transport = RequestsTransport(app_id, app_token, base_url)
        return PBNClient(transport)
