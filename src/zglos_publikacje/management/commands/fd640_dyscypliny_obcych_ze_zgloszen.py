"""FD#640: raport (i opcjonalnie usunięcie) dyscyplin dopisanych przez
formularz zgłaszania publikacji autorom spoza uczelni.

Domyślnie tylko wypisuje znalezione przypadki. ``--usun`` usuwa przypisania
dyscyplin oraz powiązania z jednostkami założone wyłącznie przez zgłoszenia
(z wpisami w historii autora). Logika: ``zglos_publikacje.fd640``.
"""

from django.core.management.base import BaseCommand, CommandError

from bpp.models import Uczelnia
from zglos_publikacje.fd640 import usun, znajdz_przypadki


class Command(BaseCommand):
    help = (
        "FD#640: pokazuje dyscypliny dopisane podczas zgłaszania prac autorom "
        "spoza uczelni; z --usun usuwa je (razem z powiązaniami z jednostkami "
        "założonymi wyłącznie przez zgłoszenia)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--uczelnia",
            help="Skrót uczelni (wymagany, gdy w bazie jest więcej niż jedna).",
        )
        parser.add_argument(
            "--usun",
            action="store_true",
            help="Usuń znalezione przypisania (domyślnie tylko raport).",
        )

    def _uczelnia(self, skrot):
        if skrot:
            try:
                return Uczelnia.objects.get(skrot=skrot)
            except Uczelnia.DoesNotExist as e:
                raise CommandError(f"Nie ma uczelni o skrócie {skrot!r}.") from e
        uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        if uczelnia is None:
            raise CommandError("Podaj --uczelnia (w bazie nie ma jednej uczelni).")
        return uczelnia

    def handle(self, *args, uczelnia=None, **options):
        uczelnia = self._uczelnia(uczelnia)
        przypadki = znajdz_przypadki(uczelnia)
        for p in przypadki:
            ad = p.przypisanie
            self.stdout.write(
                f"{p.autor} (id {p.autor.pk}): {ad.dyscyplina_naukowa} na rok {ad.rok}"
            )
            self.stdout.write(f"    {p.opis_utworzenia}")
            for aj in p.jednostki_ze_zgloszen:
                self.stdout.write(f"    jednostka ze zgłoszenia: {aj.jednostka}")
            if options["usun"]:
                usun(p)
                self.stdout.write("    → usunięto")
        self.stdout.write(
            f"Przypadków: {len(przypadki)}"
            + ("" if options["usun"] else " (tylko raport; usuwa --usun)")
        )
