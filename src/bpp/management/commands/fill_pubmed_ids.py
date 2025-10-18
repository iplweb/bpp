from django.core.management import BaseCommand

from bpp.models.cache import Rekord
from bpp.models.system import Jezyk
from bpp.views.api.pubmed import get_data_from_ncbi, parse_data_from_ncbi


class Command(BaseCommand):
    help = "Pobiera PubMed IDs dla wszystkich angielskich publikacji 2013-2015"

    def handle(self, *args, **options):
        for rec in Rekord.objects.filter(
            jezyk=Jezyk.objects.get(skrot="ang."), rok__in=[2013, 2014, 2015]
        ):
            orig = rec.original
            if orig.pubmed_id:
                continue

            print("Pobieram: %r" % orig.tytul_oryginalny)

            xml = get_data_from_ncbi(orig.tytul_oryginalny)
            if len(xml) == 1:
                data = parse_data_from_ncbi(xml[0])
                print(data)

                changed = False

                if data.get("pubmed_id"):
                    orig.pubmed_id = data.get("pubmed_id")
                    changed = True

                if data.get("doi"):
                    orig.doi = data.get("doi")
                    changed = True

                if changed:
                    orig.save()
