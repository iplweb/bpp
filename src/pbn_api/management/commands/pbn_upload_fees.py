from pbn_api.integrator import wyslij_informacje_o_platnosciach
from pbn_api.management.commands.util import PBNBaseCommand


class Command(PBNBaseCommand):
    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        client = self.get_client(app_id, app_token, base_url, user_token)
        wyslij_informacje_o_platnosciach(client)
