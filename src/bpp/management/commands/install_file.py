# -*- encoding: utf-8 -*-


import importlib
import os
from django.core.management import BaseCommand
import sys
from bpp import models

class Command(BaseCommand):
    help = """Instaluje plik w danym obiekcie o danym PK
    Parametry:
    filename: nazwa pliku,
    model: nazwa modelu z bpp.models,
    pk: primary key tegoz modelu,
    field_name: pole, gdzie obraz zostanie wgrany
    """

    def handle(self, filename, model, pk, field_name, *args, **options):
        assert(os.path.exists(filename) and os.path.isfile(filename)), \
            "sciezka '%s' nie istnieje lub nie jest plikiem" % filename
        try:
            m = getattr(models, model)
        except AttributeError:
            print("Model '%s' nie zdefiniowany w bpp.models" % model)
            sys.exit(-1)

        try:
            obj = m.objects.get(pk=pk)
        except m.DoesNotExist:
            print("Obiekt '%s' o id %s nie istnieje." % (model, pk))
            sys.exit(-1)

        from django.core.files import File
        fld = getattr(obj, field_name)
        fld.save(os.path.basename(filename), File(open(filename, 'rb')))
