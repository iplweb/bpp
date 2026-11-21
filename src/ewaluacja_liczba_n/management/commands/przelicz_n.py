from django.core.management import BaseCommand, CommandError

from bpp.models import Uczelnia
from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_liczba_n.models import domyslny_okres
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_okresu


class Command(BaseCommand):
    """Wymusza przeliczenie liczby N dla uczelni z użyciem nowej aplikacji
    ewaluacja_liczba_n — dla wskazanego okresu ewaluacji."""

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--uczelnia-id",
            type=int,
            default=None,
            help="ID uczelni (domyślnie: pierwsza uczelnia w bazie)",
        )
        parser.add_argument(
            "--okres",
            type=int,
            default=None,
            metavar="ROK_OD",
            help="Pierwszy rok okresu ewaluacji, np. 2022 albo 2026 "
            "(domyślnie: okres zawierający bieżący rok)",
        )

    def handle(self, *args, **options):
        uczelnia_id = options.get("uczelnia_id")
        if uczelnia_id:
            uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
        else:
            uczelnia = Uczelnia.objects.get()

        rok_od = options.get("okres")
        if rok_od is None:
            okres = domyslny_okres()
        else:
            try:
                okres = OkresEwaluacji.objects.get(rok_od=rok_od)
            except OkresEwaluacji.DoesNotExist as e:
                raise CommandError(
                    f"Brak okresu ewaluacji zaczynającego się w {rok_od} r."
                ) from e

        self.stdout.write(f"Przeliczam liczby N dla uczelni (okres {okres})...")
        oblicz_liczby_n_dla_okresu(uczelnia, okres=okres)
        self.stdout.write(self.style.SUCCESS("Przeliczono liczby N pomyślnie!"))
