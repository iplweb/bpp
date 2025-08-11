from django.db import transaction
from tqdm import tqdm

from pbn_api.importer import utworz_autorow
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Jednostka, Rekord


class Command(PBNBaseCommand):
    @transaction.atomic
    def handle(self, verbosity=1, *args, **options):

        client = self.get_client(
            options["app_id"],
            options["app_token"],
            options["base_url"],
            options["user_token"],
        )

        updates = False
        qset = Rekord.objects.all()
        for elem in tqdm(qset, total=qset.count()):
            bpp_orig = elem.original
            pbn_orig = elem.pbn_uid

            if pbn_orig is None:
                print(f"Brak odpowiednika w PBN dla rekordu {bpp_orig=}")
                continue

            pbn_json = pbn_orig.current_version["object"]

            pbn_autorzy = pbn_json.get("authors", {})
            pbn_redaktorzy = pbn_json.get("editors", {})
            suma = len(pbn_autorzy) + len(pbn_redaktorzy)

            if suma != bpp_orig.autorzy_set.count():
                updates = True
                utworz_autorow(
                    bpp_orig,
                    pbn_json,
                    client,
                    Jednostka.objects.get(nazwa="Jednostka Domyślna"),
                )

        if updates:
            print("Uruchom pbn_integruj_oswiadczenia")
