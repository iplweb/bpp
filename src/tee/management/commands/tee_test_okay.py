from django.core.management import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):

        self.stderr.write("wrote to stderr")
        self.stdout.write("wrote to stdout")
        print("Used print()")
        print("Used print() with file=self.stderr", file=self.stderr)
