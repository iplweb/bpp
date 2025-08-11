from pbn_api import integrator
from pbn_api.management.commands.util import PBNBaseCommand


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, app_id, app_token, base_url, user_token, *args, **kw):
        client = self.get_client(
            app_id=app_id, app_token=app_token, base_url=base_url, user_token=user_token
        )

        integrator.pobierz_zrodla_mnisw(client)
