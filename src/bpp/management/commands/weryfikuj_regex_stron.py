# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand

from bpp.models.abstract import strony_regex, BRAK_PAGINACJI
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = "Weryfikuje regex strony_regex dla pola 'Szczegoly' wydawnictw ciągłych i zwartych"

    def handle(self, *args, **options):
        for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
            q = klass.objects.exclude(szczegoly="").exclude(szczegoly=None).filter(rok__gte=2010)
        total = q.count()
        ret = []
        cnt = 0
        for elem in q.only("pk", "tytul_oryginalny", "szczegoly"):

            cnt = False
            for bp in BRAK_PAGINACJI:
                if elem.szczegoly.find(bp) >= 0:
                    cnt = True
                    break

            if cnt:
                continue

            parsed = strony_regex.search(elem.szczegoly)
            if parsed is None or parsed.groupdict()['poczatek'] is None:
                print(elem.pk, "|", elem.szczegoly, "|", elem.tytul_oryginalny)
