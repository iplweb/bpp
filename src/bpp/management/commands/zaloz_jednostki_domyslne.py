"""
Likwiduje jednostki organizacyjne w wydziałach danej uczelni i zakłada
w ich miejsce jedną "jednostkę domyślną" na każdy wydział.

Założenie: likwidowane jednostki są PUSTE (bez zatrudnień, publikacji,
patentów i prac doktorskich). Jeżeli którakolwiek nie jest pusta —
komenda przerywa z błędem i NIC nie kasuje. Przeniesieniem danych z
niepustych jednostek zajmuje się osobno `remap_jednostka`.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Jednostka,
    Patent_Autor,
    Praca_Doktorska,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
    Wydzial,
)


class Command(BaseCommand):
    help = (
        "Dla każdego wydziału podanej uczelni zakłada jedną 'jednostkę "
        "domyślną' i kasuje pozostałe (puste) jednostki tego wydziału. "
        "Jeżeli któraś jednostka nie jest pusta — przerywa z błędem.\n\n"
        "Przykłady:\n"
        "  python manage.py zaloz_jednostki_domyslne UAFM --dry-run\n"
        "  python manage.py zaloz_jednostki_domyslne UAFM"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "skrot_uczelni",
            type=str,
            help="Skrót uczelni (Uczelnia.skrot), np. UAFM",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaż co się stanie, ale nic nie zapisuj (rollback na końcu)",
        )

    def powiazania_blokujace(self, jednostka):
        """Zwraca {opis: liczba} dla niepustych powiązań CASCADE.

        Każde z tych powiązań kasuje przy DELETE realne dane (zatrudnienia,
        przypisania autorów do publikacji, prace doktorskie, a w przypadku
        ``aktualna_jednostka`` — samego autora). Pusty dict == jednostkę
        można bezpiecznie usunąć.
        """
        liczniki = {
            "zatrudnienia (Autor_Jednostka)": Autor_Jednostka.objects.filter(
                jednostka=jednostka
            ).count(),
            "aktualna jednostka autora": Autor.objects.filter(
                aktualna_jednostka=jednostka
            ).count(),
            "wyd. ciągłe (autorzy)": Wydawnictwo_Ciagle_Autor.objects.filter(
                jednostka=jednostka
            ).count(),
            "wyd. zwarte (autorzy)": Wydawnictwo_Zwarte_Autor.objects.filter(
                jednostka=jednostka
            ).count(),
            "patenty (autorzy)": Patent_Autor.objects.filter(
                jednostka=jednostka
            ).count(),
            "prace doktorskie": Praca_Doktorska.objects.filter(
                jednostka=jednostka
            ).count(),
        }
        return {opis: n for opis, n in liczniki.items() if n}

    def _przerwij_jesli_niepuste(self, likwidowane):
        """Walidacja 'wszystko albo nic': żadna jednostka nie może mieć danych."""
        niepuste = [
            (jednostka, powiazania)
            for jednostka in likwidowane
            if (powiazania := self.powiazania_blokujace(jednostka))
        ]
        if not niepuste:
            return

        self.stderr.write(
            self.style.ERROR(
                "Następujące jednostki NIE są puste — przerwano, nic nie skasowano:"
            )
        )
        for jednostka, powiazania in niepuste:
            opis = ", ".join(f"{k}: {v}" for k, v in powiazania.items())
            self.stderr.write(
                f"  [{jednostka.pk}] {jednostka.nazwa} ({jednostka.skrot}) — {opis}"
            )
        raise CommandError(
            f"{len(niepuste)} jednostek nie jest pustych. Najpierw "
            "przenieś z nich dane (np. komendą remap_jednostka)."
        )

    def _przerwij_jesli_osierocone(self, do_usuniecia):
        """Bezpiecznik: żadna usuwana jednostka nie może być rodzicem jednostki
        spoza zakresu usuwania (parent ma on_delete=CASCADE → cichy kask)."""
        osierocone = Jednostka.objects.filter(parent__in=do_usuniecia).exclude(
            pk__in=do_usuniecia.values_list("pk", flat=True)
        )
        if not osierocone.exists():
            return

        self.stderr.write(
            self.style.ERROR(
                "Usuwane jednostki są rodzicami jednostek spoza zakresu "
                "(kasowanie pociągnęłoby je kaskadą) — przerwano:"
            )
        )
        for jednostka in osierocone:
            self.stderr.write(
                f"  [{jednostka.pk}] {jednostka.nazwa} (parent: {jednostka.parent_id})"
            )
        raise CommandError("Rozwiąż hierarchię jednostek i uruchom ponownie.")

    @transaction.atomic
    def handle(self, *args, **options):
        skrot = options["skrot_uczelni"]
        dry_run = options["dry_run"]

        try:
            uczelnia = Uczelnia.objects.get(skrot=skrot)
        except Uczelnia.DoesNotExist as err:
            raise CommandError(f"Uczelnia o skrócie '{skrot}' nie istnieje.") from err

        wydzialy = list(Wydzial.objects.filter(uczelnia=uczelnia).order_by("nazwa"))
        if not wydzialy:
            raise CommandError(f"Uczelnia '{skrot}' nie ma żadnych wydziałów.")

        # Faza B (#438): „wydział" = węzeł-lustro (root Jednostka). Mapujemy
        # każdy Wydzial na jego węzeł-korzeń; jednostki „w wydziale" =
        # poddrzewo (self-FK ``wydzial`` == węzeł).
        from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

        wezly = {w.pk: znajdz_lub_utworz_wezel_wydzialu(w)[0] for w in wydzialy}

        # Jednostki kandydujące do likwidacji: te w poddrzewach wydziałów tej
        # uczelni. Jednostki bez wydziału (np. obca_jednostka) zostają nietknięte.
        likwidowane = Jednostka.objects.filter(
            uczelnia=uczelnia, wydzial__in=list(wezly.values())
        )
        if uczelnia.obca_jednostka_id:
            likwidowane = likwidowane.exclude(pk=uczelnia.obca_jednostka_id)

        # 1) Walidacja pustości — wszystko albo nic.
        self._przerwij_jesli_niepuste(likwidowane)

        # 2) Załóż jednostkę domyślną dla każdego wydziału.
        #    Nazwa BEZ odmiany — nazwy wydziałów już zawierają słowo "Wydział".
        zachowane_pk = []
        for wydzial in wydzialy:
            wezel = wezly[wydzial.pk]
            # Jednostka domyślna wisi pod węzłem-lustrem wydziału (denorm
            # ``wydzial`` = ten węzeł-korzeń).
            target, utworzona = Jednostka.objects.get_or_create(
                uczelnia=uczelnia,
                nazwa=f"Jednostka Domyślna - {wydzial.nazwa}",
                defaults=dict(
                    skrot=f"JD-{wydzial.skrot}",
                    parent=wezel,
                    aktualna=True,
                    widoczna=True,
                    skupia_pracownikow=True,
                ),
            )
            zachowane_pk.append(target.pk)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {'utworzono' if utworzona else 'istnieje'}: "
                    f"[{target.pk}] {target.nazwa}"
                )
            )

        # 3) Usuń stare jednostki (poza świeżo założonymi domyślnymi).
        do_usuniecia = likwidowane.exclude(pk__in=zachowane_pk)
        self._przerwij_jesli_osierocone(do_usuniecia)

        for jednostka in do_usuniecia.order_by("nazwa"):
            self.stdout.write(
                f"  usuwam: [{jednostka.pk}] {jednostka.nazwa} ({jednostka.skrot})"
            )
        ile_usunieto, _ = do_usuniecia.delete()
        self.stdout.write(self.style.SUCCESS(f"\nUsunięto jednostek: {ile_usunieto}."))

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(
                self.style.WARNING(
                    "[DRY RUN] wszystkie zmiany wycofane — nic nie zapisano."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Gotowe."))
