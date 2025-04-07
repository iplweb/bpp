from tqdm import tqdm

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Punktacja_Zrodla, Wydawnictwo_Ciagle


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **kw):
        seen = set()

        for elem in tqdm(Wydawnictwo_Ciagle.objects.filter(rok__gte=2022)):
            try:
                elem.punkty_kbn = elem.zrodlo.punktacja_zrodla_set.get(
                    rok=elem.rok
                ).punkty_kbn
            except Punktacja_Zrodla.DoesNotExist:
                zrodlo_rok = (elem.zrodlo.pk, elem.rok)
                if zrodlo_rok not in seen:
                    print(f"Brak punktacji dla {elem.zrodlo} za {elem.rok}")
                    seen.add(zrodlo_rok)
                continue

            elem.save()
