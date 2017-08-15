# -*- encoding: utf-8 -*-
# save me as yourapp/management/commands/upload_file_to_model.py

from argparse import FileType
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.core.files.base import File

class Command(BaseCommand):
    help = 'Uploads a file to a given field in a given model'

    def add_arguments(self, parser):
        parser.add_argument("app")
        parser.add_argument("model")
        parser.add_argument("pk")
        parser.add_argument("field")
        parser.add_argument("path", type=FileType('rb'))

    def handle(self, *args, **options):
        obj = ContentType.objects.get_by_natural_key(
            options['app'].lower(),
            options['model'].lower()
        ).get_object_for_this_type(pk=options['pk'])

        try:
            field = getattr(obj, options['field'])
        except AttributeError as e:
            fields = [field.name for field in obj._meta.get_fields()]
            fields = ", ".join(fields)
            e.args = (e.args[0] + f". Available names: {fields}", )
            raise e

        field.save(
            name=Path(options['path'].name).name,
            content=File(options['path']))
        obj.save()
