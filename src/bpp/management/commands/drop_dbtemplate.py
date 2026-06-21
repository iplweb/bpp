"""Usuń wiersz(e) dbtemplate z bazy, żeby renderowanie spadło na zawsze
aktualny plik z dysku — i przebuduj zależny ``opis_bibliograficzny_cache``.

Dlaczego to nie jest zwykłe ``Template.objects.filter(...).delete()``:

1. ``SzablonDlaOpisuBibliograficznego.template`` jest ``on_delete=PROTECT``,
   a migracja zasiewa domyślne powiązanie ``model=None`` -> ``opis_...``.
   Bez wcześniejszego usunięcia tego powiązania ``Template.delete()`` rzuca
   ``ProtectedError``.
2. ``opis_bibliograficzny_cache`` to pole ``@denormalized``, które NIE zależy
   od dbtemplate. Samo usunięcie wiersza nie odświeży zapisanego stringa —
   trzeba wymusić ``rebuild_instances_of_models`` (a trigger ``bpp_refresh_cache``
   dociągnie kopię w ``Rekord``).
"""

from dbtemplates.models import Template
from django.core.management.base import BaseCommand
from django.db import transaction

from bpp.dbtemplates_sync import wyczysc_cache_dbtemplate
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)
from bpp.util import rebuild_instances_of_models


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
        modele_do_przebudowy = set()

        for name in options["template_names"]:
            template = Template.objects.filter(name=name).first()
            if template is None:
                self.stderr.write(
                    self.style.WARNING(
                        f"Szablon '{name}' nie istnieje w bazie — pomijam."
                    )
                )
                continue

            # Modele zależne MUSZĄ być policzone PRZED usunięciem powiązań,
            # bo get_models_for_template czyta tabelę SzablonDlaOpisu...
            modele = SzablonDlaOpisuBibliograficznego.objects.get_models_for_template(
                template
            )
            modele_do_przebudowy.update(modele)

            # 1. Zdejmij PROTECT-ujące powiązania.
            usuniete, _ = SzablonDlaOpisuBibliograficznego.objects.filter(
                template=template
            ).delete()
            # 2. Usuń sam wiersz dbtemplate -> get_template spada na dysk.
            template.delete()
            # 3. Wyczyść cache dbtemplates/CachedLoader, inaczej loader nadal
            #    serwowałby usuniętą treść (i przebudowa cache renderowałaby
            #    stary szablon zamiast dyskowego).
            wyczysc_cache_dbtemplate(name)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Usunięto '{name}' (oraz {usuniete} powiązań Szablonu)."
                )
            )

        # 3. Przebuduj cache z dysku (chyba że poproszono o pominięcie).
        if options["skip_rebuild"]:
            return
        if not modele_do_przebudowy:
            self.stdout.write(
                "Brak modeli zależnych od usuniętych szablonów — bez przebudowy."
            )
            return
        self.stdout.write(
            f"Przebudowa opis_bibliograficzny_cache dla {len(modele_do_przebudowy)} "
            "modeli (z dysku)…"
        )
        # rebuild_instances_of_models tylko ZNACZY instancje jako dirty
        # (DirtyInstance); realne przeliczenie robi denorm.flush(). Admin
        # świadomie odkłada flush na noc, ale komenda deployowa ma odświeżyć
        # cache od ręki.
        rebuild_instances_of_models(list(modele_do_przebudowy))
        from denorm import denorms

        denorms.flush()
        self.stdout.write(self.style.SUCCESS("Gotowe."))
