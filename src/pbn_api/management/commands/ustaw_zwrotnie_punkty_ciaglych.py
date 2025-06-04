from tqdm import tqdm

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Punktacja_Zrodla, Wydawnictwo_Ciagle


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--min-rok", type=int, default=2022)

    def handle(self, min_rok, *args, **kw):
        seen = set()

        for elem in tqdm(Wydawnictwo_Ciagle.objects.filter(rok__gte=min_rok)):
            try:
                elem.punkty_kbn = elem.zrodlo.punktacja_zrodla_set.get(
                    rok=elem.rok
                ).punkty_kbn
            except Punktacja_Zrodla.DoesNotExist:
                zrodlo_rok = (elem.zrodlo.pk, elem.rok)
                if zrodlo_rok not in seen:
                    print(
                        f"Brak punktacji dla {elem.zrodlo} za {elem.rok}, przyznaję 5 punktów"
                    )
                    seen.add(zrodlo_rok)
                elem.punkty_kbn = 5

            elem.save()
