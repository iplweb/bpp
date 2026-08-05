from django.core.management.base import BaseCommand

from oauth_mcp.tasks import DCR_RETENCJA_DNI, usun_osierocone_aplikacje_dcr


class Command(BaseCommand):
    help = (
        "Kasuje osierocone rejestracje DCR (klienci MCP, którzy zarejestrowali "
        "się i nigdy nie dokończyli flow). Aplikacje z jakimkolwiek tokenem, "
        "grantem lub id-tokenem są nietykalne."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--starsze-niz",
            type=int,
            default=DCR_RETENCJA_DNI,
            metavar="DNI",
            help=f"Próg retencji w dniach (domyślnie {DCR_RETENCJA_DNI}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Policz, ale nie kasuj — audyt wolumenu przed przebiegiem.",
        )
        parser.add_argument(
            "--uwzglednij-nieoznaczone",
            action="store_true",
            help=(
                "Obejmij też rejestracje sprzed wprowadzenia prefiksu `dcr-`, "
                "rozpoznawane heurystycznie (public + authorization-code + "
                "brak właściciela). KRUCHE — używaj razem z --dry-run."
            ),
        )

    def handle(self, *args, **options):
        # Logika żyje w tasks.usun_osierocone_aplikacje_dcr — ta sama ścieżka
        # kodu, co zadanie cykliczne Celery, żeby komenda i beat nie mogły się
        # rozjechać.
        n = usun_osierocone_aplikacje_dcr(
            dni=options["starsze_niz"],
            dry_run=options["dry_run"],
            uwzglednij_nieoznaczone=options["uwzglednij_nieoznaczone"],
        )
        czasownik = "Do skasowania" if options["dry_run"] else "Skasowano"
        self.stdout.write(f"{czasownik} osieroconych rejestracji DCR: {n}")
