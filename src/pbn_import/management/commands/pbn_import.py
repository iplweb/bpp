"""Modern PBN import command using ImportManager with interactive CLI."""

import questionary
from django.contrib.auth import get_user_model

from bpp.models import Uczelnia
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_import.models import ImportSession
from pbn_import.utils import ImportManager
from pbn_import.utils.step_definitions import (
    ALL_STEP_DEFINITIONS,
    get_command_steps,
)

User = get_user_model()

# Import steps from single source of truth (step_definitions.py)
IMPORT_STEPS = get_command_steps()


def build_config_from_options(options):
    """Build session config dict from command line options.

    Maps form_field options (e.g., --disable-zrodla) to disable_key config
    (e.g., disable_zrodla) using step_definitions as the source of truth.
    """
    config = {
        "app_id": options.get("app_id"),
        "base_url": options.get("base_url"),
        "delete_existing": options.get("delete_existing", False),
        "wydzial_domyslny": options.get("wydzial_domyslny"),
        "wydzial_domyslny_skrot": options.get("wydzial_domyslny_skrot"),
    }

    # Map form_field to disable_key from step_definitions
    for step in ALL_STEP_DEFINITIONS:
        form_field = step["form_field"]
        disable_key = step["disable_key"]
        # Get option value using form_field name (from CLI --disable-{form_field})
        config[disable_key] = options.get(f"disable_{form_field}", False)

    return config


class Command(PBNBaseCommand):
    help = "Import data from PBN using the modern import system"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Bez interaktywnego menu (dla skryptów/automatyzacji)",
        )

        # Opcje disable-* dla kompatybilności wstecznej i trybu batch
        for key, label in IMPORT_STEPS:
            parser.add_argument(
                f"--disable-{key}",
                action="store_true",
                help=f"Pomiń: {label}",
            )

        # Dodatkowe opcje
        parser.add_argument(
            "--delete-existing",
            action="store_true",
            help="Usuń istniejące publikacje PBN",
        )
        parser.add_argument(
            "--wydzial-domyslny",
            default="Wydział Domyślny",
            help="Domyślna nazwa wydziału",
        )
        parser.add_argument(
            "--wydzial-domyslny-skrot",
            help="Skrót domyślnego wydziału",
        )
        parser.add_argument(
            "--username",
            help="Nazwa użytkownika dla sesji importu (domyślnie: pierwszy superuser)",
        )

    def run_interactive(self, options):
        """Uruchom interaktywny wybór opcji."""
        self.stdout.write(self.style.SUCCESS("\n=== Import PBN ===\n"))

        # Wybór etapów importu
        choices = [
            questionary.Choice(
                title=label,
                value=key,
                checked=not options.get(f"disable_{key}", False),
            )
            for key, label in IMPORT_STEPS
        ]

        selected = questionary.checkbox(
            "Wybierz etapy importu:",
            choices=choices,
            instruction="(spacja = zaznacz/odznacz, Enter = potwierdź)",
        ).ask()

        if selected is None:
            self.stdout.write("Anulowano.")
            return None

        # Ustaw opcje disable_* na podstawie wyboru
        for key, _ in IMPORT_STEPS:
            options[f"disable_{key}"] = key not in selected

        # Pytanie o usunięcie istniejących
        if not options.get("delete_existing"):
            delete_answer = questionary.confirm(
                "Usunąć istniejące publikacje PBN?",
                default=False,
            ).ask()

            if delete_answer is None:
                self.stdout.write("Anulowano.")
                return None

            options["delete_existing"] = delete_answer

        # Wyświetl podsumowanie
        self.stdout.write("\nWybrane etapy:")
        for key, label in IMPORT_STEPS:
            if not options.get(f"disable_{key}"):
                self.stdout.write(f"  ✓ {label}")
            else:
                self.stdout.write(f"  ✗ {label} (pominięty)")

        if options.get("delete_existing"):
            self.stdout.write(
                self.style.WARNING("\n  ⚠ Istniejące publikacje PBN zostaną usunięte!")
            )

        # Potwierdzenie
        confirm = questionary.confirm(
            "\nRozpocząć import?",
            default=True,
        ).ask()

        if not confirm:
            self.stdout.write("Anulowano.")
            return None

        return options

    def _get_import_user(self, options):
        """Pobierz użytkownika dla sesji importu."""
        if options.get("username"):
            return User.objects.get(username=options["username"])

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stderr.write("Nie znaleziono superusera. Użyj --username")
            return None
        return user

    def _ensure_pbn_integration(self):
        """Włącz integrację PBN jeśli wyłączona."""
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia and not uczelnia.pbn_integracja:
            uczelnia.pbn_integracja = True
            uczelnia.save(update_fields=["pbn_integracja"])

    def _display_results(self, results, session):
        """Wyświetl wyniki importu."""
        self.stdout.write(self.style.SUCCESS("\n=== Import zakończony pomyślnie ==="))

        for step_name, result in results.items():
            if isinstance(result, dict):
                if "error" in result:
                    self.stdout.write(f"  {step_name}: {self.style.ERROR('BŁĄD')}")
                else:
                    self.stdout.write(f"  {step_name}: {self.style.SUCCESS('OK')}")

        self.stdout.write(f"\n  Czas trwania: {session.duration}")

    def handle(self, *args, **options):
        # Domyślnie tryb interaktywny, chyba że --noinput
        if not options.get("noinput"):
            options = self.run_interactive(options)
            if options is None:
                return

        # Pobierz użytkownika dla sesji
        user = self._get_import_user(options)
        if user is None:
            return

        # Włącz integrację PBN jeśli wyłączona
        self._ensure_pbn_integration()

        # Utwórz klienta PBN używając PBNBaseCommand.get_client()
        client = self.get_client(
            app_id=options["app_id"],
            app_token=options["app_token"],
            base_url=options["base_url"],
            user_token=options["user_token"],
        )

        # Utwórz sesję importu z config z step_definitions
        session = ImportSession.objects.create(
            user=user,
            status="pending",
            config=build_config_from_options(options),
        )

        self.stdout.write(f"Utworzono sesję importu {session.id}")

        # Utwórz i uruchom managera importu
        manager = ImportManager(session=session, client=client, config=session.config)

        try:
            self.stdout.write("Rozpoczynam import...")
            results = manager.run()
            self._display_results(results, session)

        except Exception as e:
            self.stderr.write(f"\n{self.style.ERROR('Import nieudany:')}")
            self.stderr.write(str(e))

            if session.error_message:
                self.stderr.write("\nSzczegóły błędu:")
                self.stderr.write(session.error_message)

            raise
