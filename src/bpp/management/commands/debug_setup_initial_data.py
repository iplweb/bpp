from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import BppUser, Uczelnia


class Command(BaseCommand):
    help = "Creates admin account and Uczelnia for debugging/testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--nazwa",
            default="",
            help="Uczelnia name (required unless --show-current)",
        )
        parser.add_argument(
            "--skrot",
            default="",
            help="Uczelnia abbreviation (required unless --show-current)",
        )
        parser.add_argument(
            "--nazwa-dopelniacz",
            default="",
            help="Uczelnia name in genitive case (dopełniacz)",
        )
        parser.add_argument(
            "--pbn-api-root",
            default="https://pbn.nauka.gov.pl",
            help="PBN API URL (default: https://pbn.nauka.gov.pl)",
        )
        parser.add_argument("--pbn-app-name", default="", help="PBN app name")
        parser.add_argument("--pbn-app-token", default="", help="PBN app token")
        parser.add_argument(
            "--username",
            default="admin",
            help="Admin username (default: admin)",
        )
        parser.add_argument(
            "--email",
            default="michal.dtz@gmail.com",
            help="Admin email (default: michal.dtz@gmail.com)",
        )
        parser.add_argument(
            "--password",
            default="foobar123",
            help="Admin password (default: foobar123)",
        )
        parser.add_argument(
            "--pbn-token",
            default="",
            help="PBN token to set for all users in BppUser table",
        )
        parser.add_argument(
            "--show-current",
            action="store_true",
            help="Show current database values as CLI command (read-only)",
        )

    def _build_uczelnia_cmd_parts(self, uczelnia):
        """Build command parts for Uczelnia fields."""
        cmd_parts = []
        field_mappings = [
            ("nazwa", "--nazwa"),
            ("skrot", "--skrot"),
            ("nazwa_dopelniacz_field", "--nazwa-dopelniacz"),
            ("pbn_api_root", "--pbn-api-root"),
            ("pbn_app_name", "--pbn-app-name"),
            ("pbn_app_token", "--pbn-app-token"),
        ]
        for attr, flag in field_mappings:
            value = getattr(uczelnia, attr)
            if value:
                cmd_parts.append(f'    {flag} "{value}"')
        return cmd_parts

    def _show_current(self):
        """Display current database values as a CLI command."""
        uczelnia = Uczelnia.objects.first()
        if not uczelnia:
            self.stdout.write(
                self.style.WARNING("No Uczelnia found in database. Nothing to show.")
            )
            return

        # Find admin user or first superuser
        admin = BppUser.objects.filter(username="admin").first()
        if not admin:
            admin = BppUser.objects.filter(is_superuser=True).first()

        # Find any user with pbn_token set
        user_with_pbn_token = BppUser.objects.exclude(pbn_token="").first()

        # Build the command
        cmd_parts = [
            "uv run python src/manage.py debug_setup_initial_data",
        ]

        # Add username and email if admin exists
        if admin:
            cmd_parts.append(f'    --username "{admin.username}"')
            if admin.email:
                cmd_parts.append(f'    --email "{admin.email}"')

        # Add Uczelnia fields
        cmd_parts.extend(self._build_uczelnia_cmd_parts(uczelnia))

        # Add pbn_token if any user has it
        if user_with_pbn_token:
            cmd_parts.append(f'    --pbn-token "{user_with_pbn_token.pbn_token}"')

        # Output the command with backslash continuation
        output = " \\\n".join(cmd_parts)
        self.stdout.write(output)

    @transaction.atomic
    def handle(self, *_args, **options):
        # Handle --show-current option first
        if options["show_current"]:
            self._show_current()
            return

        # Validate required arguments when not in show-current mode
        if not options["nazwa"]:
            self.stderr.write(
                self.style.ERROR("--nazwa is required unless using --show-current")
            )
            return
        if not options["skrot"]:
            self.stderr.write(
                self.style.ERROR("--skrot is required unless using --show-current")
            )
            return

        # Create or get admin user
        admin, created = BppUser.objects.get_or_create(
            username=options["username"],
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "email": options["email"],
            },
        )
        if not created:
            admin.email = options["email"]
        admin.set_password(options["password"])
        admin.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            f"{action} admin user '{options['username']}' "
            f"with password '{options['password']}'"
        )

        # Create Uczelnia
        uczelnia, created = Uczelnia.objects.get_or_create(
            nazwa=options["nazwa"],
            defaults={
                "skrot": options["skrot"],
                "nazwa_dopelniacz_field": options["nazwa_dopelniacz"],
                "pbn_api_root": options["pbn_api_root"],
                "pbn_app_name": options["pbn_app_name"],
                "pbn_app_token": options["pbn_app_token"],
                "pbn_integracja": True,
            },
        )

        if not created:
            # Update existing
            uczelnia.skrot = options["skrot"]
            uczelnia.nazwa_dopelniacz_field = options["nazwa_dopelniacz"]
            uczelnia.pbn_api_root = options["pbn_api_root"]
            uczelnia.pbn_app_name = options["pbn_app_name"]
            uczelnia.pbn_app_token = options["pbn_app_token"]
            uczelnia.pbn_integracja = True
            uczelnia.save()

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} Uczelnia '{options['nazwa']}'")

        # Update pbn_token for all users if provided
        if options["pbn_token"]:
            from django.utils import timezone

            updated = BppUser.objects.update(
                pbn_token=options["pbn_token"], pbn_token_updated=timezone.now()
            )
            self.stdout.write(f"Set pbn_token for {updated} user(s)")
