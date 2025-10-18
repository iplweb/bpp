from django.core.management import BaseCommand
from django.db import transaction
from thefuzz import fuzz
from tqdm import tqdm
from unidecode import unidecode

from bpp.models import Jednostka
from pbn_api.models import OswiadczenieInstytucji


class Command(BaseCommand):
    """
    Sprawdza czy każde OswiadczeniaInstytucji ma swoje odwzorowanie w rekordzie publikacji, jeżeli nie
    to próbuje automatycznie to naprawić.
    """

    @transaction.atomic
    def handle(self, *args, **options):
        seen = set()

        for oi in tqdm(OswiadczenieInstytucji.objects.all()):
            rec = oi.get_bpp_publication()

            if rec is None:
                if oi.publicationId_id not in seen:
                    print(
                        "BRAK ODPOWIEDNIKA REKORDU W BPP DLA OSWIADCZENIA: ",
                        oi.publicationId.year,
                        oi.publicationId.mongoId,
                        oi.publicationId,
                    )
                seen.add(oi.publicationId_id)
                continue

            au = oi.get_bpp_autor()

            if au.pk in rec.autorzy_set.values_list("autor_id", flat=True):
                # Sprawdź datę oświadczenia
                wa = oi.get_bpp_wa()
                if oi.statedTimestamp != wa.data_oswiadczenia:
                    wa.data_oswiadczenia = oi.statedTimestamp
                    wa.save()

                continue

            found = False
            for rec_au in rec.autorzy_set.all():
                au_data = unidecode(au.nazwisko), unidecode(au.imiona)
                rec_au_data = (
                    unidecode(rec_au.autor.nazwisko),
                    unidecode(rec_au.autor.imiona),
                )

                podobienstwo_nazwisko = fuzz.ratio(au_data[0], rec_au_data[0])
                podobienstwo_imiona = fuzz.ratio(au_data[1], rec_au_data[1])

                if podobienstwo_nazwisko >= 80 and (
                    podobienstwo_imiona >= 80
                    or fuzz.partial_ratio(au_data[1], rec_au_data[1]) >= 80
                ):
                    found = True

                    old_autor = rec_au.autor

                    rec_au.autor = au
                    rec_au.afiliuje = True
                    rec_au.zatrudniony = True

                    old_jednostka = rec_au.jednostka

                    if not rec_au.jednostka.skupia_pracownikow:
                        if au.aktualna_jednostka.skupia_pracownikow:
                            rec_au.jednostka = au.aktualna_jednostka
                        else:
                            # Dowolna, ale nie obca
                            rec_au.jednostka = Jednostka.objects.get(
                                nazwa="Jednostka Domyślna"
                            )

                    old_dyscyplina = rec_au.dyscyplina_naukowa
                    rec_au.dyscyplina_naukowa = oi.get_bpp_discipline()

                    rec_au.data_oswiadczenia = oi.statedTimestamp

                    print(
                        f"PRZEMAPOWUJE: {rec}: {old_autor} -> {au}, {old_jednostka} -> {rec_au.jednostka}, "
                        f"{old_dyscyplina} -> {rec_au.dyscyplina_naukowa}"
                    )
                    rec_au.save()
                    continue

            if not found:
                print(
                    f"BRAK AUTORA W REKORDZIE: {rec}, brak autorwa {au}, lista autorow "
                    f"{[str(wa.autor) for wa in rec.autorzy_set.all()]}"
                )
                continue
