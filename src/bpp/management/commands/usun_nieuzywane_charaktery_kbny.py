# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db.models import CharField, TextField, Q
from django.apps import apps
from bpp.models import Sumy, Typ_KBN, Charakter_Formalny
from bpp.util import usun_nieuzywany_typ_charakter


class Command(BaseCommand):
    help = "Usuwa nieuzywane charaktery formalne i typy KBN (stosuj po imporcie z DBF)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, dry_run=False, *args, **options):
        usun_nieuzywany_typ_charakter(Typ_KBN, "typ_kbn", dry_run)
        usun_nieuzywany_typ_charakter(Charakter_Formalny, "charakter_formalny", dry_run)
