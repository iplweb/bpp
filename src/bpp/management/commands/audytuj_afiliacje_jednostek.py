"""#438 — audyt afiliacji do jednostek nieprzyjmujących afiliacji.

Po konwersji Wydział→Jednostka (``konwertuj_wydzialy_na_jednostki``) mogą
istnieć wiersze przypisań autorów z ``afiliuje=True`` wskazujące jednostki
rodzaju „Wydział" (``RodzajJednostki.autor_moze_afiliowac=False``). Takie
wiersze są semantycznie błędne (autor nie afiliuje do samego wydziału) i nie
przejdą walidacji przy najbliższej edycji.

Komenda skanuje WSZYSTKIE konkretne modele przypisań autorów (podklasy
``BazaModeluOdpowiedzialnosciAutorow``) i raportuje takie wiersze. Z opcją
``--napraw`` odznacza w nich ``afiliuje`` (spójnie z obsługą jednostki obcej,
gdzie afiliacja też jest zdejmowana).
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from bpp.models.abstract.authors import BazaModeluOdpowiedzialnosciAutorow


def _modele_przypisan_autorow():
    """Konkretne (nie-abstrakcyjne) modele przypisań autorów."""
    return sorted(
        (
            m
            for m in apps.get_models()
            if issubclass(m, BazaModeluOdpowiedzialnosciAutorow)
            and not m._meta.abstract
        ),
        key=lambda m: m.__name__,
    )


class Command(BaseCommand):
    help = (
        "Raportuje wiersze przypisań autorów z afiliuje=True wskazujące "
        "jednostki, których rodzaj nie dopuszcza afiliacji (np. „Wydział”). "
        "Z --napraw odznacza afiliuje w takich wierszach."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--napraw",
            action="store_true",
            help=(
                "Odznacz afiliuje w błędnych wierszach "
                "(domyślnie tylko raport, bez modyfikacji)."
            ),
        )

    def handle(self, *args, napraw=False, **options):
        laczna = 0
        naprawionych = 0

        for model in _modele_przypisan_autorow():
            qs = model.objects.filter(
                afiliuje=True,
                jednostka__rodzaj__autor_moze_afiliowac=False,
            )
            count = qs.count()
            if not count:
                continue

            laczna += count
            self.stdout.write(
                f"{model.__name__}: {count} wiersz(y) z afiliuje=True do "
                "jednostki nieprzyjmującej afiliacji:"
            )
            for wa in qs.select_related("autor", "jednostka", "jednostka__rodzaj"):
                self.stdout.write(
                    f"  - id={wa.pk} rekord={wa.rekord_id} "
                    f"autor={wa.autor} jednostka=„{wa.jednostka}” "
                    f"(rodzaj: {wa.jednostka.rodzaj})"
                )

            if napraw:
                naprawionych += qs.update(afiliuje=False)

        if laczna == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "Brak błędnych afiliacji — wszystkie przypisania z "
                    "afiliuje=True wskazują jednostki przyjmujące afiliację."
                )
            )
            return

        if napraw:
            self.stdout.write(
                self.style.WARNING(
                    f"Naprawiono {naprawionych} wiersz(y) (afiliuje=False). "
                    "Jeśli afiliacja wpływa na wyświetlane dane, przelicz "
                    "cache rekordów (denorm)."
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"Znaleziono {laczna} błędny(ch) wiersz(y). Uruchom "
                    "z --napraw, aby odznaczyć afiliuje."
                )
            )
