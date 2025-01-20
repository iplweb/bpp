from pbn_api import importer
from pbn_api.management.commands.util import PBNBaseCommand


class Command(PBNBaseCommand):
    def handle(self, verbosity=1, *args, **options):
        importer.importuj_wydawcow(verbosity=verbosity)
