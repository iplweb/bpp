import arrow
from django.db import transaction

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Jezyk, Rekord
from bpp.util import pbar


class Command(PBNBaseCommand):
    """Nadpisuje wszystkie dyscypliny dla zrodel z odpowiednikami z PBNu"""

    @transaction.atomic
    def handle(self, verbosity=1, *args, **options):
        for rekord in pbar(Rekord.objects.exclude(pbn_uid_id=None)):
            original = rekord.original
            if original.streszczenia.exists():
                continue

            publication = original.pbn_uid
            versions = sorted(
                publication.versions,
                key=lambda obj: arrow.get(obj["createdTime"]),
                reverse=True,
            )
            for elem in versions:
                abstracts = elem.get("object").get("abstracts")
                if abstracts:
                    for lang_code, text in abstracts.items():
                        try:
                            jezyk_streszczenia = Jezyk.objects.get(pbn_uid_id=lang_code)
                        except Jezyk.DoesNotExist:
                            print(
                                f"\n\nNIE zaimportowano streszczenia - brak takiego jezyka w systemie jak {lang_code}"
                            )
                            continue

                        original.streszczenia.create(
                            jezyk_streszczenia=jezyk_streszczenia, streszczenie=text
                        )

                    print(
                        f"Zaimportowano {len(abstracts)} streszczen dla rekordu {original} "
                        f"ze snapshotu {elem['createdTime']}"
                    )
                    break
