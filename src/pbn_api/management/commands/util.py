from django.core.management import BaseCommand

from pbn_api.client import PBNClient, RequestsTransport
from pbn_api.conf import settings

from bpp.models import Uczelnia


class PBNBaseCommand(BaseCommand):
    def add_arguments(self, parser):

        app_id = getattr(settings, "PBN_CLIENT_APP_ID")
        app_token = getattr(settings, "PBN_CLIENT_APP_TOKEN")
        base_url = getattr(settings, "PBN_CLIENT_BASE_URL")
        user_token = None

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if uczelnia.pbn_app_name:
                app_id = uczelnia.pbn_app_name
            if uczelnia.pbn_app_token:
                app_token = uczelnia.pbn_app_token
            if uczelnia.pbn_api_root:
                base_url = uczelnia.pbn_api_root
            if uczelnia.pbn_api_user_id:
                user_token = uczelnia.pbn_api_user.pbn_token

        parser.add_argument("--app-id", default=app_id)
        parser.add_argument("--app-token", default=app_token)
        parser.add_argument("--base-url", default=base_url)
        parser.add_argument("--user-token", default=user_token)

    def get_client(self, app_id, app_token, base_url, user_token, verbose=False):
        transport = RequestsTransport(app_id, app_token, base_url, user_token)
        if verbose:
            print("App ID\t\t", app_id)
            print("App token\t", app_token)
            print("Base URL\t", base_url)
            print("User token\t", user_token)
        return PBNClient(transport)
