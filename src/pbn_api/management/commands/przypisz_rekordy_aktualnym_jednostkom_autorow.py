from tqdm import tqdm

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


class Command(PBNBaseCommand):
    def handle(self, *args, **kw):

        for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
            for elem in tqdm(klass.objects.all()):
                for wa in elem.autorzy_set.all():
                    if (
                        wa.autor.aktualna_jednostka
                        and wa.jednostka != wa.autor.aktualna_jednostka
                        and wa.autor.aktualna_jednostka.skupia_pracownikow is True
                    ):
                        wa.jednostka = wa.autor.aktualna_jednostka
                        wa.save()
