# -*- encoding: utf-8 -*-
# https://djangosnippets.org/snippets/10614/

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

        field = getattr(obj, options['field'])
        field.save(
            name=Path(options['path'].name).name,
            content=File(options['path']))
        obj.save()
