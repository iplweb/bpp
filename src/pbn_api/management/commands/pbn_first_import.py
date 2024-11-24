import django

django.setup()

from pbn_api import importer
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import integruj_jezyki, integruj_kraje, pobierz_zrodla_mnisw
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


class Command(PBNBaseCommand):
    def send_progress(self, msg):
        print(msg)

    #    @transaction.atomic
    def handle(self, app_id, app_token, base_url, user_token, *args, **kw):
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        if False:
            integruj_jezyki(client, create_if_not_exists=True)
            integruj_kraje(client)
            client.download_disciplines()
            client.sync_disciplines()

            pobierz_zrodla_mnisw(client)
        importer.importuj_zrodla()
