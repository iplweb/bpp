from django.core.management import BaseCommand

from tee import core


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("command_name", help="Django command to execute")

    def handle(self, command_name, *args, **options):
        core.call_command(command_name, *args, **options)
