"""Demo data for docs/uzytkownik/powiazania-autorow.md (the co-author network).

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-powiazania-autorow.py

The network is read from a precomputed table that production refreshes
nightly (celerybeat, 4:00). A fresh demo DB has it empty, so the author page
shows no "Zobacz sieć powiązań" button. This script:

1. adds Yennefer Merigold's two closest co-authors to more of her articles
   (idempotent enough: a rerun just thickens the same two lines further),
   so the graph shows clearly thicker lines next to thin ones,
2. recomputes the whole table (same code as the nightly task).
"""

from django.db import transaction
from django.db.models import Q

from bpp.models import Autor, BppUser, Wydawnictwo_Ciagle
from powiazania_autorow.core import calculate_author_connections
from powiazania_autorow.models import AuthorConnection

# Autorka powiązana z kontem „yennefer” (krok 2 w docs/deweloper/zrzuty-ekranu.md).
# Nie po pk: klucze główne zależą od tego, czy baza była już wcześniej zapełniana.
YENNEFER = (
    BppUser.objects.filter(username="yennefer", autor__isnull=False)
    .values_list("autor_id", flat=True)
    .first()
)
if YENNEFER is None:
    raise SystemExit(
        "Brak konta „yennefer” powiązanego z autorem — załóż je wg kroku 2 "
        "w docs/deweloper/zrzuty-ekranu.md."
    )
# how many more joint articles for her 1st and 2nd closest co-author
DOPISZ = [8, 4]

calculate_author_connections()

with transaction.atomic():
    yen = Autor.objects.get(pk=YENNEFER)
    najblizsi = [
        c.secondary_author if c.primary_author_id == YENNEFER else c.primary_author
        for c in AuthorConnection.objects.filter(
            Q(primary_author=yen) | Q(secondary_author=yen)
        ).order_by("-shared_publications_count", "pk")[: len(DOPISZ)]
    ]
    prace = list(
        Wydawnictwo_Ciagle.objects.filter(autorzy_set__autor=yen)
        .distinct()
        .order_by("-rok", "pk")
    )
    for wsp, ile in zip(najblizsi, DOPISZ, strict=True):
        jednostka = wsp.aktualna_jednostka or yen.aktualna_jednostka
        dodane = 0
        for praca in prace:
            if dodane >= ile:
                break
            if praca.autorzy_set.filter(autor=wsp).exists():
                continue
            praca.dodaj_autora(wsp, jednostka)
            dodane += 1
        print(f"{wsp}: +{dodane} wspólnych prac")

print("powiazan:", calculate_author_connections())
