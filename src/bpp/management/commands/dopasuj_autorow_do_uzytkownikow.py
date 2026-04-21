from django.core.management.base import BaseCommand

from bpp.models import BppUser


class Command(BaseCommand):
    help = (
        "Próbuje automatycznie dopasować autorów do"
        " użytkowników (po emailu lub imieniu/nazwisku)."
    )

    def handle(self, *args, **options):
        dopasowani = 0
        niedopasowani = 0

        users = BppUser.objects.filter(autor__isnull=True)
        self.stdout.write(f"Użytkownicy bez autora: {users.count()}")

        for user in users:
            user.sprobuj_dopasowac_autora()
            user.refresh_from_db()
            if user.autor_id:
                self.stdout.write(self.style.SUCCESS(f"  {user} -> {user.autor}"))
                dopasowani += 1
            else:
                self.stdout.write(f"  {user} -> brak dopasowania")
                niedopasowani += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDopasowano: {dopasowani}, niedopasowanych: {niedopasowani}"
            )
        )
