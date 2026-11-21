"""Management command: generuj_plik_polon_demo.

Zapisuje fałszywy eksport POL-on („Rozszerzone zestawienie pracowników
podmiotu") dla uczelni z ISTNIEJĄCEJ bazy demo (wygenerowanej przez
``create_demo_data`` albo odtworzonej z dumpa). Baza nie jest modyfikowana —
powstaje tylko plik XLSX do zaimportowania przez „operacje → import z POLON".
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from bpp.demo_data.generators.polon import parsuj_dyscypliny, write_polon_file
from bpp.demo_data.themes.registry import THEMES, get_theme
from bpp.models import Uczelnia


class Command(BaseCommand):
    help = (
        "Zapisuje falszywy plik POL-on (Rozszerzone zestawienie pracownikow "
        "podmiotu) dla uczelni demo. Tylko odczyt bazy; wynik to plik XLSX."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            type=str,
            default=None,
            help="Plik albo katalog docelowy (domyslnie: biezacy katalog, "
            "nazwa jak w prawdziwym eksporcie).",
        )
        parser.add_argument(
            "--dyscypliny",
            nargs="+",
            default=None,
            metavar="NAZWA[=FTE]",
            help="Dyscypliny z celem FTE N na rok (domyslnie: filozofia=16, "
            "'nauki teologiczne=5', biotechnologia=15, archeologia=14).",
        )
        parser.add_argument("--bez-blednych-wierszy", action="store_true")
        parser.add_argument(
            "--bez-orcid",
            action="store_true",
            help="Nie wpisuj falszywych ORCID autorom, ktorzy go nie maja.",
        )
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument(
            "--uczelnia",
            type=str,
            default=None,
            help="Skrot uczelni (domyslnie: pierwsza uczelnia w bazie).",
        )
        parser.add_argument(
            "--motyw",
            type=str,
            default=None,
            choices=sorted(THEMES),
            help="Motyw demo (dla nazwy 'obcej' uczelni; domyslnie zgadywany).",
        )

    def handle(self, *args, **options):
        if options["uczelnia"]:
            try:
                uczelnia = Uczelnia.objects.get(skrot=options["uczelnia"])
            except Uczelnia.DoesNotExist as e:
                raise CommandError(
                    f"Brak uczelni o skrocie '{options['uczelnia']}'."
                ) from e
        else:
            uczelnia = None

        try:
            podsumowanie = write_polon_file(
                options["out"],
                uczelnia=uczelnia,
                dyscypliny=parsuj_dyscypliny(options["dyscypliny"]),
                seed=options["seed"],
                bledne_wiersze=not options["bez_blednych_wierszy"],
                theme=get_theme(options["motyw"]) if options["motyw"] else None,
                orcid=not options["bez_orcid"],
            )
        except ValueError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(podsumowanie.tekst())
