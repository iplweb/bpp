# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db.models import get_models, CharField, TextField, Q
from bpp.models import Sumy


class Command(BaseCommand):
    help = 'Szuka nieuzywanych pol we wszystkich modelach'

    def handle(self, *args, **options):
        for model in get_models():

            if model._meta.app_label != 'bpp' or \
                model._meta.object_name in ['Jednostka', 'Wydzial'] or \
                model._meta.object_name.find('View') >= 0 or \
                model == Sumy:
                continue

            total = model.objects.all().count()
            for field in model._meta.fields:
                if (type(field)!=CharField and type(field)!=TextField) or \
                    field.name in ['adnotacje', 'slowa_kluczowe']:
                    continue

                check = model.objects.filter(
                    Q(**{field.name: None}) | Q(**{field.name:''})).count()
                if check == total:
                    print "Nieuzywane pole: ", model, field
