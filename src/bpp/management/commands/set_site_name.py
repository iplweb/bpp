from optparse import OptionError

from django.contrib.sites.models import Site
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Ustawia nazwę domeny i strony internetowej"

    def add_arguments(self, parser):
        parser.add_argument("-d", "--domain", action="store")
        parser.add_argument("-n", "--name", action="store")

    def handle(self, *args, **options):
        kw = {}
        for elem in "domain", "name":
            if options[elem]:
                kw[elem] = options[elem]

        if not kw:
            raise OptionError("Podaj parametr --domain, --name lub oba!", "domain")

        if Site.objects.all().count() != 1:
            raise ValueError(
                "To polecenie jest przeznaczone tylko dla sytuacji, gdy jest jeden obiekt Site w systemie"
            )

        s = Site.objects.all()[0]
        [setattr(s, attr, value) for attr, value in list(kw.items())]
        s.save()
