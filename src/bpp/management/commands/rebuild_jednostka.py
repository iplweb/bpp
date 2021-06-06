# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand

from bpp.models import Jednostka


class Command(BaseCommand):
    help = "Weryfikuje prace bez autorow"

    def handle(self, *args, **options):
        Jednostka.objects.rebuild()
