from decimal import Decimal

from django.core.management.base import BaseCommand

from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025
from ewaluacja_metryki.utils import generuj_metryki

from bpp.models import Uczelnia


class Command(BaseCommand):
    help = "Oblicza metryki ewaluacyjne dla autorów na podstawie algorytmu plecakowego"

    def add_arguments(self, parser):
        parser.add_argument(
            "--autor-id", type=int, help="ID konkretnego autora do przeliczenia"
        )
        parser.add_argument(
            "--dyscyplina-id", type=int, help="ID konkretnej dyscypliny do przeliczenia"
        )
        parser.add_argument(
            "--jednostka-id", type=int, help="ID konkretnej jednostki do przeliczenia"
        )
        parser.add_argument(
            "--rok-min",
            type=int,
            default=2022,
            help="Początkowy rok okresu ewaluacji (domyślnie 2022)",
        )
        parser.add_argument(
            "--rok-max",
            type=int,
            default=2025,
            help="Końcowy rok okresu ewaluacji (domyślnie 2025)",
        )
        parser.add_argument(
            "--minimalny-pk",
            type=float,
            default=0.01,
            help="Minimalny próg punktów (domyślnie 0.01)",
        )
        parser.add_argument(
            "--nadpisz", action="store_true", help="Nadpisz istniejące metryki"
        )
        parser.add_argument(
            "--bez-liczby-n",
            action="store_true",
            help="Pomiń przeliczanie liczby N (domyślnie przelicza)",
        )
        parser.add_argument(
            "--rodzaje-autora",
            nargs="+",
            choices=["N", "D", "Z", " "],
            default=["N", "D", "Z", " "],
            help=(
                "Rodzaje autorów do przetworzenia (N=pracownik, D=doktorant, Z=inny zatrudniony, ' '=brak danych). "
                "Domyślnie: wszystkie"
            ),
        )

    def handle(self, *args, **options):
        rok_min = options["rok_min"]
        rok_max = options["rok_max"]
        minimalny_pk = Decimal(str(options["minimalny_pk"]))
        nadpisz = options["nadpisz"]
        bez_liczby_n = options["bez_liczby_n"]
        rodzaje_autora = options.get("rodzaje_autora", ["N", "D", "Z", " "])

        # Krok 1: Przelicz liczby N, chyba że pominięto
        if not bez_liczby_n:
            self.stdout.write(
                self.style.WARNING("Krok 1/2: Przeliczanie liczby N dla uczelni...")
            )
            try:
                uczelnia = Uczelnia.objects.get_default()
                oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
                self.stdout.write(
                    self.style.SUCCESS("✓ Przeliczono liczby N pomyślnie")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Błąd przy przeliczaniu liczby N: {str(e)}")
                )
                self.stdout.write(
                    self.style.WARNING(
                        "Kontynuuję obliczanie metryk mimo błędu liczby N..."
                    )
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Pominięto przeliczanie liczby N (opcja --bez-liczby-n)"
                )
            )

        # Krok 2: Oblicz metryki
        self.stdout.write(
            self.style.WARNING(
                f"Krok 2/2: Obliczanie metryk dla okresu {rok_min}-{rok_max}"
            )
        )
        self.stdout.write(f"Minimalny próg punktów: {minimalny_pk}")

        # Wyświetl informację o rodzajach autorów
        rodzaje_nazwy = {
            "N": "Pracownicy (N)",
            "D": "Doktoranci (D)",
            "Z": "Inni zatrudnieni (Z)",
            " ": "Brak danych",
        }
        rodzaje_str = ", ".join([rodzaje_nazwy.get(r, r) for r in rodzaje_autora])
        self.stdout.write(f"Rodzaje autorów: {rodzaje_str}")

        # Filtruj IloscUdzialowDlaAutoraZaCalosc
        ilosc_udzialow_qs = IloscUdzialowDlaAutoraZaCalosc.objects.all()

        if options["autor_id"]:
            ilosc_udzialow_qs = ilosc_udzialow_qs.filter(autor_id=options["autor_id"])
        if options["dyscyplina_id"]:
            ilosc_udzialow_qs = ilosc_udzialow_qs.filter(
                dyscyplina_naukowa_id=options["dyscyplina_id"]
            )

        # Dodaj filtr po jednostce jeśli podano
        if options["jednostka_id"]:
            from bpp.models import Autor_Jednostka

            autor_ids = (
                Autor_Jednostka.objects.filter(jednostka_id=options["jednostka_id"])
                .values_list("autor_id", flat=True)
                .distinct()
            )
            ilosc_udzialow_qs = ilosc_udzialow_qs.filter(autor_id__in=autor_ids)

        # Wywołaj wspólną funkcję generuj_metryki
        wynik = generuj_metryki(
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=minimalny_pk,
            nadpisz=nadpisz,
            rodzaje_autora=rodzaje_autora,
            logger_output=self.stdout,
            ilosc_udzialow_queryset=ilosc_udzialow_qs,
        )

        # Wyświetl podsumowanie
        self.stdout.write(
            self.style.SUCCESS(
                f"\nZakończono: przetworzono {wynik['processed']}, "
                f"pominięto {wynik['skipped']}, błędy {wynik['errors']}"
            )
        )
