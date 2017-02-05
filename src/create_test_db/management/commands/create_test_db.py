# -*- encoding: utf-8 -*-
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Tworzy testową bazę danych (polecenie do użytku przez dewelopera)"""

    def handle(self, *args, **options):
        call_command("test", "create_test_db.tests", "--keepdb", "-v 2")