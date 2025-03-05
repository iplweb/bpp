from django.db import transaction

from pbn_api.integrator import integruj_oswiadczenia_pbn_first_import
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Jednostka


class Command(PBNBaseCommand):
    @transaction.atomic
    def handle(self, verbosity=1, *args, **options):

        client = self.get_client(
            options["app_id"],
            options["app_token"],
            options["base_url"],
            options["user_token"],
        )

        integruj_oswiadczenia_pbn_first_import(
            client,
            default_jednostka=Jednostka.objects.get(nazwa="Jednostka Domyślna"),
        )
