from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025
from ewaluacja_metryki.models import MetrykaAutora

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

    def handle(self, *args, **options):
        rok_min = options["rok_min"]
        rok_max = options["rok_max"]
        minimalny_pk = Decimal(str(options["minimalny_pk"]))
        nadpisz = options["nadpisz"]
        bez_liczby_n = options["bez_liczby_n"]

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

        total = ilosc_udzialow_qs.count()
        self.stdout.write(f"Znaleziono {total} autorów do przetworzenia")

        processed = 0
        skipped = 0
        errors = 0

        for ilosc_udzialow in ilosc_udzialow_qs.select_related(
            "autor", "dyscyplina_naukowa"
        ):
            autor = ilosc_udzialow.autor
            dyscyplina = ilosc_udzialow.dyscyplina_naukowa
            slot_maksymalny = ilosc_udzialow.ilosc_udzialow

            # Sprawdź czy metryka już istnieje
            if (
                not nadpisz
                and MetrykaAutora.objects.filter(
                    autor=autor, dyscyplina_naukowa=dyscyplina
                ).exists()
            ):
                skipped += 1
                continue

            try:
                with transaction.atomic():
                    # Pobierz główną jednostkę autora
                    from bpp.models import Autor_Jednostka

                    jednostka = None
                    aj = Autor_Jednostka.objects.filter(
                        autor=autor, podstawowe_miejsce_pracy=True
                    ).first()
                    if aj:
                        jednostka = aj.jednostka

                    # Oblicz metryki algorytmem plecakowym
                    punkty_nazbierane, prace_nazbierane_ids, slot_nazbierany = (
                        autor.zbieraj_sloty(
                            zadany_slot=slot_maksymalny,
                            rok_min=rok_min,
                            rok_max=rok_max,
                            minimalny_pk=minimalny_pk,
                            dyscyplina_id=dyscyplina.pk,
                        )
                    )

                    # Oblicz metryki dla wszystkich prac
                    punkty_wszystkie, prace_wszystkie_ids, slot_wszystkie = (
                        autor.zbieraj_sloty(
                            zadany_slot=slot_maksymalny,
                            rok_min=rok_min,
                            rok_max=rok_max,
                            minimalny_pk=minimalny_pk,
                            dyscyplina_id=dyscyplina.pk,
                            akcja="wszystko",
                        )
                    )

                    # Utwórz lub zaktualizuj metrykę
                    metryka, created = MetrykaAutora.objects.update_or_create(
                        autor=autor,
                        dyscyplina_naukowa=dyscyplina,
                        defaults={
                            "jednostka": jednostka,
                            "slot_maksymalny": slot_maksymalny,
                            "slot_nazbierany": Decimal(str(slot_nazbierany)),
                            "punkty_nazbierane": Decimal(str(punkty_nazbierane)),
                            "prace_nazbierane": prace_nazbierane_ids,
                            "slot_wszystkie": Decimal(str(slot_wszystkie)),
                            "punkty_wszystkie": Decimal(str(punkty_wszystkie)),
                            "prace_wszystkie": prace_wszystkie_ids,
                            "liczba_prac_wszystkie": len(prace_wszystkie_ids),
                            "rok_min": rok_min,
                            "rok_max": rok_max,
                        },
                    )

                    action = "utworzono" if created else "zaktualizowano"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{processed + 1}/{total}] {action} metrykę dla {autor} - {dyscyplina.nazwa}: "
                            f"nazbierane {punkty_nazbierane:.2f} pkt / {slot_nazbierany:.2f} slotów, "
                            f"średnia {metryka.srednia_za_slot_nazbierana:.2f} pkt/slot"
                        )
                    )
                    processed += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Błąd przy przetwarzaniu {autor} - {dyscyplina.nazwa}: {str(e)}"
                    )
                )
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nZakończono: przetworzono {processed}, pominięto {skipped}, błędy {errors}"
            )
        )
