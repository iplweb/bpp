from bpp.models import Uczelnia
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import Scientist
from pbn_integrator.utils import pobierz_ludzi_z_uczelni


class Command(PBNBaseCommand):
    help = (
        "Ustawi wszystkim pbn_api.Scientist from_institution_api=False, a następnie "
        'pobierze naukowców za pomocą funkcji "pobierz_ludzi_z_uczelni"'
    )

    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        # 1) ustawi wszystkim pbn_api.Scientist from_institution_api=False
        self.stdout.write("Ustawiam wszystkim Scientist from_institution_api=False...")
        updated_count = Scientist.objects.update(from_institution_api=False)
        self.stdout.write(f"Zaktualizowano {updated_count} rekordów.")

        # 2) pobierze naukowców za pomocą funkcji "pobierz_ludzi_z_uczelni"
        client = self.get_client(app_id, app_token, base_url, user_token)
        uczelnia = Uczelnia.objects.get_default()

        if uczelnia.pbn_uid_id is None:
            raise Exception("Uczelnia nie ma ustawionego pbn_uid_id")

        self.stdout.write(
            f"Pobieram ludzi z uczelni {uczelnia.nazwa} (PBN UID: {uczelnia.pbn_uid_id})..."
        )
        pobierz_ludzi_z_uczelni(client, uczelnia.pbn_uid_id)

        # Sprawdź wyniki
        scientists_from_api = Scientist.objects.filter(
            from_institution_api=True
        ).count()
        self.stdout.write(
            f"Zakończono. Liczba naukowców z from_institution_api=True: {scientists_from_api}"
        )
