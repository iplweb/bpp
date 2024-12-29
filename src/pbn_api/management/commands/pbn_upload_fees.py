from pbn_api.integrator import wyslij_informacje_o_platnosciach
from pbn_api.management.commands.util import PBNBaseCommand


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--rok", type=int)

    def handle(self, app_id, app_token, base_url, user_token, rok, *args, **options):
        client = self.get_client(app_id, app_token, base_url, user_token)
        wyslij_informacje_o_platnosciach(client, rok)
