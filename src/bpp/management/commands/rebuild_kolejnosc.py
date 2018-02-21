# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor
from bpp.models.cache import Rekord


class Command(BaseCommand):
    """
    Polecenie porządkujące kolejności autorów

    Ustaw kolejność pierwszego autora na „0”, uprządkuj następujące po sobie
    kolejności, upewnij się, że nie ma luk, etc…
    """
    help = 'Upewnia sie, ze wartosc pola "kolejnosc" dla autorow wydawnictw ciaglych ' \
           'i zwartych jest poprawna, tzn. zaczyna sie od zera i jest ponumerowana w ' \
           'sposob ciagly.'

    # NIE robimy tego w transakcji, aby nie przyblokować bazy danyc na dłuższy czas
    # @transaction.atomic
    def handle(self, *args, **options):
        # Jeżeli będziemy to robić z włączonym cache, dojdzie do przyblokowania
        # kolejki RabbitMQ. Realnie renumeracja kolejności nie pociąga za sobą zmiany
        # w opisach bibliograficznych, więc musimy to wyłączyć:
        from bpp.models import cache
        cache.disable()

        for klass in [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor]:
            if options['verbosity'] >= 2:
                print(klass)

            old_id = None
            # Taki porządek sortowania, bo jeżeli się trafią dwa rekordy z tą
            # samą kolejnością, to ten o mniejszym ID ma pierwszeństwo
            q = klass.objects.all().order_by("rekord_id", "kolejnosc", "id")

            for elem in q:

                if old_id != elem.rekord_id:
                    old_id = elem.rekord_id
                    next_kolejnosc = 0
                    pre = "---"

                if next_kolejnosc != elem.kolejnosc:
                    if options['verbosity'] >= 2:
                        if pre is not None:
                            print(pre)
                        pre = None
                        print(elem.rekord_id, elem.id, "kolejnosc", elem.kolejnosc, ":=", next_kolejnosc)
                    elem.kolejnosc = next_kolejnosc
                    elem.save()

                next_kolejnosc += 1
