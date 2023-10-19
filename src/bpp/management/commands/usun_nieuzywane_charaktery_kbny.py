import argparse

from django.core.management import BaseCommand

from bpp.models import Charakter_Formalny, Typ_KBN
from bpp.util import usun_nieuzywany_typ_charakter


class Command(BaseCommand):
    help = "Usuwa nieuzywane charaktery formalne i typy KBN (stosuj po imporcie z DBF)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction)

    def handle(self, dry_run, *args, **options):
        usun_nieuzywany_typ_charakter(Typ_KBN, "typ_kbn", dry_run)
        usun_nieuzywany_typ_charakter(Charakter_Formalny, "charakter_formalny", dry_run)
