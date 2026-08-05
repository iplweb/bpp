"""Zapewnij obcą jednostkę dla każdej uczelni w systemie (multi-hosted).

W multi-hosted wszystkie uczelnie współdzielą jedną bazę, a ``Jednostka.nazwa`` /
``skrot`` są ``unique=True`` globalnie. Obca jednostka MUSI więc być per-uczelnia
(nazwa "Obca jednostka <SKRÓT>") i ustawiona jako ``Uczelnia.obca_jednostka``.
To polecenie provisionuje / naprawia ten stan hurtem. Nie wymusza podpięcia
obcej jednostki do wydziału — uczelnie mogą nie używać wydziałów, a gate
``sprawdz_obca_jednostka`` tego nie wymaga (triggery spójności zdjęto w #438).
"""

from django.core.management.base import BaseCommand, CommandError

from bpp.models import Uczelnia
from pbn_import.utils.institution_import import (
    sprawdz_obca_jednostka,
    znajdz_lub_utworz_obca_jednostke,
)


class Command(BaseCommand):
    help = (
        "Zapewnia obcą jednostkę (per-uczelnia) i ustawia FK "
        "Uczelnia.obca_jednostka dla każdej uczelni. Idempotentne. "
        "--dry-run tylko raportuje braki."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "uczelnia",
            nargs="?",
            default=None,
            help="Opcjonalnie: pk lub slug jednej uczelni (domyślnie wszystkie).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Tylko raportuj braki (bez zapisów). Kończy z kodem !=0, gdy "
                "którakolwiek uczelnia wymaga naprawy."
            ),
        )

    def _wybierz_uczelnie(self, identyfikator):
        if identyfikator is None:
            return Uczelnia.objects.all().order_by("pk")

        qs = Uczelnia.objects.all()
        if identyfikator.isdigit():
            uczelnia = qs.filter(pk=int(identyfikator)).first()
        else:
            uczelnia = qs.filter(slug=identyfikator).first()
        if uczelnia is None:
            raise CommandError(f"Nie znaleziono uczelni: {identyfikator}")
        return [uczelnia]

    def handle(self, *args, **options):
        uczelnie = self._wybierz_uczelnie(options["uczelnia"])
        dry_run = options["dry_run"]

        problemy = 0
        for uczelnia in uczelnie:
            if dry_run:
                problem = sprawdz_obca_jednostka(uczelnia)
                if problem:
                    problemy += 1
                    self.stdout.write(
                        self.style.WARNING(f"[BRAK] {uczelnia}: {problem}")
                    )
                else:
                    self.stdout.write(f"[OK]   {uczelnia}")
                continue

            obca, created = znajdz_lub_utworz_obca_jednostke(uczelnia)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"[UTWORZONO] {uczelnia}: {obca.nazwa}")
                )
            else:
                self.stdout.write(f"[OK]   {uczelnia}: {obca.nazwa}")

        if dry_run and problemy:
            raise CommandError(
                f"{problemy} uczelni wymaga naprawy — uruchom bez --dry-run."
            )
