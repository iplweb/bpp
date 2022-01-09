import sys

from django.core.management import BaseCommand

from tee import core


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("command_name", help="Django command to execute")
        parser.add_argument("otherthings", nargs="*")  # parser.add

    def handle(self, command_name, otherthings, *args, **options):
        new_argv = [sys.argv[0], command_name] + otherthings

        kwargs = {}

        for elem in ["stdout", "stderr"]:
            if options.get(elem):
                kwargs[elem] = options.get(elem)

        core.execute(new_argv, **kwargs)
