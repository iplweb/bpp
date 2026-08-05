"""Usuń wiersz(e) dbtemplate z bazy (render spada na plik z dysku) i przebuduj
zależny ``opis_bibliograficzny_cache``.

Po wyrwaniu opisu z dbtemplates (#329) ``SzablonDlaOpisuBibliograficznego`` nie
ma już FK do ``Template`` — trzyma tylko ``nazwa_szablonu``. Komenda przestała
więc kasować powiązania; kasuje sam wiersz dbtemplate (z guardem dysk-existence)
i przebudowuje denorm dla modeli mapowanych na tę nazwę."""

from django.core.management.base import BaseCommand
from django.db import transaction

from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


class Command(BaseCommand):
    help = (
        "Usuwa wiersz(e) dbtemplate z bazy (render spada na plik z dysku) i "
        "przebudowuje zależny opis_bibliograficzny_cache."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "template_names",
            nargs="+",
            help="Nazwy szablonów do usunięcia, np. opis_bibliograficzny.html",
        )
        parser.add_argument(
            "--skip-rebuild",
            action="store_true",
            help="Nie przebudowuj opis_bibliograficzny_cache (sam usuń wiersze).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        for name in options["template_names"]:
            modele = (
                []
                if options["skip_rebuild"]
                else SzablonDlaOpisuBibliograficznego.objects.get_models_for_szablon(
                    name
                )
            )
            usunieto = usun_dbtemplate_i_przebuduj(
                name, modele, flush=True, log=self.stdout.write
            )
            if usunieto:
                self.stdout.write(self.style.SUCCESS(f"Przetworzono '{name}'."))
            else:
                self.stderr.write(
                    self.style.WARNING(
                        f"'{name}' nie ma pliku na dysku — pominięto (guard)."
                    )
                )
