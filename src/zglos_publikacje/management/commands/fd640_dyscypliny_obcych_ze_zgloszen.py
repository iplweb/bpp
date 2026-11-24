"""FD#640: raport (i opcjonalnie usunięcie) dyscyplin dopisanych przez
formularz zgłaszania publikacji autorom spoza uczelni.

Domyślnie tylko wypisuje znalezione przypadki. ``--usun`` usuwa przypisania
dyscyplin oraz powiązania z jednostkami założone przez te same zgłoszenia
(z wpisami w historii autora). Przypisań zmienionych później przez redakcję
albo użytych w pracach nie rusza — tylko je wypisuje. Logika:
``zglos_publikacje.fd640``.
"""

from django.core.management.base import BaseCommand

from zglos_publikacje.fd640 import usun, znajdz_przypadki


class Command(BaseCommand):
    help = (
        "FD#640: pokazuje dyscypliny dopisane podczas zgłaszania prac autorom "
        "spoza uczelni; z --usun usuwa je (razem z powiązaniami z jednostkami "
        "założonymi przez te same zgłoszenia). Pomija przypisania zmienione "
        "później albo użyte w pracach."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--usun",
            action="store_true",
            help="Usuń znalezione przypisania (domyślnie tylko raport).",
        )

    def handle(self, *args, **options):
        przypadki = znajdz_przypadki()
        usuniete_jednostki = set()
        do_usuniecia = 0
        for p in przypadki:
            ad = p.przypisanie
            self.stdout.write(
                f"{p.autor} (id {p.autor.pk}): {ad.dyscyplina_naukowa} na rok {ad.rok}"
            )
            self.stdout.write(f"    {p.opis_utworzenia}")
            for aj in p.jednostki_ze_zgloszenia:
                self.stdout.write(f"    jednostka ze zgłoszenia: {aj.jednostka}")
            if p.pominiety is not None:
                self.stdout.write(f"    {p.pominiety}")
                continue
            do_usuniecia += 1
            if options["usun"]:
                usun(p, usuniete_jednostki=usuniete_jednostki)
                self.stdout.write("    → usunięto")
        self.stdout.write(
            f"Przypadków: {len(przypadki)}, do usunięcia: {do_usuniecia}"
            + ("" if options["usun"] else " (tylko raport; usuwa --usun)")
        )
