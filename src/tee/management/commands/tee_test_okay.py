from django.core.management import BaseCommand

from tee import const


class Command(BaseCommand):
    help = const.DONT_CALL

    def handle(self, *args, **options):

        self.stderr.write("wrote to stderr")
        self.stdout.write("wrote to stdout")
        print("Used print()")
        print("Used print() with file=self.stderr", file=self.stderr)
