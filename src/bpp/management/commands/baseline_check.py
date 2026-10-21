"""Bramka świeżości baseline'u — czy ``baseline.sql`` nadąża za migracjami.

Komenda o tej nazwie była wcześniej dostarczana przez ``django-pg-baseline``,
ale 0.3.1 ją usunął, zostawiając wyłącznie ``baseline_info`` — które jest
czysto informacyjne (drukuje delty i ZAWSZE kończy się zerem), więc nie może
pełnić roli bramki. Job ``baseline-check`` w ``.github/workflows/tests.yml``
padał wtedy z ``Unknown command: 'baseline_check'``.

Podmiana wołania na ``baseline_info`` byłaby gorsza niż czerwony job:
świeciłaby się na zielono zawsze, także gdy ``baseline.sql`` realnie odjedzie
od migracji — a to dokładnie ta awaria, przed którą ten gate ma chronić.

Dlatego bramka mieszka teraz tutaj, na publicznym API pakietu
(``django_pg_baseline.freshness.check_freshness``), które przetrwało zmianę.
Nazwa komendy i sygnatura ``--max-delta`` są zachowane, żeby workflow i
dokumentacja nie wymagały zmian.
"""

from django.core.management.base import BaseCommand, CommandError

DOMYSLNA_MAX_DELTA = 50


class Command(BaseCommand):
    help = (
        "Sprawdź, czy baseline.sql nie odjechał od migracji. Kończy się "
        "błędem, gdy największa delta per-app przekracza --max-delta."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-delta",
            type=int,
            default=DOMYSLNA_MAX_DELTA,
            help=(
                "Ile migracji ponad baseline wolno mieć pojedynczej aplikacji "
                f"(domyślnie {DOMYSLNA_MAX_DELTA})."
            ),
        )

    def handle(self, *args, **options):
        from django_pg_baseline.conf import get_config
        from django_pg_baseline.freshness import check_freshness

        config = get_config()

        if not config.meta_path.exists():
            raise CommandError(
                f"Brak {config.meta_path} — nie ma z czego policzyć delty. "
                "Uruchom `make rebuild-baseline` albo usuń PG_BASELINE z "
                "ustawień, jeśli baseline ma być wyłączony."
            )

        raport = check_freshness(config.meta_path)
        maks = options["max_delta"]

        self.stdout.write(f"baseline git_sha:  {raport.git_sha}")
        self.stdout.write("Delty per-app (migracje na dysku nowsze niż baseline):")
        for app, delta in sorted(raport.deltas.items(), key=lambda kv: -kv[1]):
            if delta:
                self.stdout.write(f"  {app:40s} +{delta}")

        self.stdout.write(
            f"\nNajwiększa delta: {raport.worst_delta} ({raport.worst_app}), "
            f"próg: {maks}"
        )

        if raport.worst_delta > maks:
            raise CommandError(
                f"Baseline odjechał: {raport.worst_app} ma "
                f"+{raport.worst_delta} migracji ponad baseline (próg {maks}). "
                "Odśwież baseline: `make baseline-update` (NIE gołe "
                "`manage.py baseline_update` — target make dokłada "
                "fix-baseline-search-path)."
            )

        self.stdout.write(self.style.SUCCESS("Baseline freshness OK."))
