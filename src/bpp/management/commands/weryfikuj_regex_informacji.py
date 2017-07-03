# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, parsed_informacje_regex


class Command(BaseCommand):
    help = "Weryfikuje regex abstract.parsed_informacje_regex dla pola 'Informacje' wydawnictw ciągłych"

    def handle(self, *args, **options):
        q = Wydawnictwo_Ciagle.objects.exclude(informacje="").exclude(informacje=None).filter(rok__gte=2010)
        total = q.count()
        ret = []
        cnt = 0
        for elem in q.only("pk", "tytul_oryginalny", "informacje"):
            parsed = parsed_informacje_regex.match(elem.informacje)
            if parsed is None or parsed.groupdict()['rok'] is None:
                print(elem.pk, "|", elem.informacje, "|", elem.tytul_oryginalny)
