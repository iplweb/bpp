from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import BppUser, Uczelnia


class Command(BaseCommand):
    help = "Creates admin account and Uczelnia for debugging/testing"

    def add_arguments(self, parser):
        parser.add_argument("--nazwa", required=True, help="Uczelnia name")
        parser.add_argument("--skrot", required=True, help="Uczelnia abbreviation")
        parser.add_argument(
            "--pbn-api-root",
            default="https://pbn.nauka.gov.pl",
            help="PBN API URL (default: https://pbn.nauka.gov.pl)",
        )
        parser.add_argument("--pbn-app-name", default="", help="PBN app name")
        parser.add_argument("--pbn-app-token", default="", help="PBN app token")

    @transaction.atomic
    def handle(self, *_args, **options):
        # Create or get admin user
        admin, created = BppUser.objects.get_or_create(
            username="admin",
            defaults={
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("foobar123")
        admin.save()

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} admin user with password 'foobar123'")

        # Create Uczelnia
        uczelnia, created = Uczelnia.objects.get_or_create(
            nazwa=options["nazwa"],
            defaults={
                "skrot": options["skrot"],
                "pbn_api_root": options["pbn_api_root"],
                "pbn_app_name": options["pbn_app_name"],
                "pbn_app_token": options["pbn_app_token"],
            },
        )

        if not created:
            # Update existing
            uczelnia.skrot = options["skrot"]
            uczelnia.pbn_api_root = options["pbn_api_root"]
            uczelnia.pbn_app_name = options["pbn_app_name"]
            uczelnia.pbn_app_token = options["pbn_app_token"]
            uczelnia.save()

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} Uczelnia '{options['nazwa']}'")
