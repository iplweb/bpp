# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from bpp.models import Autor, Jednostka, Wydzial, Uczelnia, Zrodlo


class Command(BaseCommand):
    help = 'Odbudowuje pola slug'

    @transaction.atomic
    def handle(self, *args, **options):
        for klass in [Autor, Jednostka, Wydzial, Uczelnia, Zrodlo]:
            for model in klass.objects.all():
                model.slug = None
                model.save()