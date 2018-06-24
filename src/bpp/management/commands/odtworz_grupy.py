# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from bpp.models import Autor, Jednostka, Wydzial, Uczelnia, Zrodlo
from bpp.system import odtworz_grupy


class Command(BaseCommand):
    help = 'Odbudowuje grupy uprawnień w sytuacji dodania nowych obiektów. ' \
           'Użyj gdy np. nie widać czegoś w Adminie, do czego użytkownik ' \
           'powinien być uprawniony.'

    @transaction.atomic
    def handle(self, *args, **options):
        odtworz_grupy()
