"""Make the Witcher demo DB slot-capable, for screenshots of points/slots reports.

Run after create_demo_data + the demo accounts (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-sloty.py

The demo generator leaves author-record links without a discipline and
authors without "rodzaj autora", so no slot is ever computed. This narrows
the demo to four disciplines (liczba N >= 12 becomes reachable), marks every
declared author as "N", snaps journal points to slot thresholds, copies the
declared discipline onto the links, renames duplicate "Yennefer Merigold"
authors (the screenshots pick her by name) and rebuilds the slot cache.
"""

from django.db import transaction

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    BppUser,
    Dyscyplina_Naukowa,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_common.models import Rodzaj_Autora

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
PROGI = [200, 140, 100, 70, 40, 20]
NAZWY = ["filozofia", "nauki teologiczne", "biotechnologia", "archeologia"]

with transaction.atomic():
    dysc = [Dyscyplina_Naukowa.objects.get(nazwa=n) for n in NAZWY]
    n = Rodzaj_Autora.objects.get(skrot="N")
    # 1. few disciplines (so liczba N >= 12 is reachable), one per author; kind "N"
    for ad in Autor_Dyscyplina.objects.all():
        ad.dyscyplina_naukowa = (
            dysc[0] if ad.autor_id == YENNEFER else dysc[ad.autor_id % len(dysc)]
        )
        ad.subdyscyplina_naukowa = None
        ad.rodzaj_autora = n
        ad.save()
    # 2. points that match a slot threshold
    for wc in Wydawnictwo_Ciagle.objects.all():
        wc.punkty_kbn = min(PROGI, key=lambda p: abs(p - float(wc.punkty_kbn or 0)))
        wc.save(update_fields=["punkty_kbn"])
    # 3. discipline on author-record links, where the author declared one that year
    ads = {
        (a.autor_id, a.rok): a.dyscyplina_naukowa_id
        for a in Autor_Dyscyplina.objects.all()
    }
    ile = 0
    for wca in Wydawnictwo_Ciagle_Autor.objects.select_related("rekord"):
        d = ads.get((wca.autor_id, wca.rekord.rok))
        if d:
            wca.dyscyplina_naukowa_id = d
            wca.przypieta = True
            wca.save()
            ile += 1
    print("powiazania z dyscyplina:", ile)
    # 4. one "Merigold Yennefer" only, so selecting her by name is unambiguous
    dup = Autor.objects.filter(imiona="Yennefer", nazwisko="Merigold").exclude(
        pk=YENNEFER
    )
    for autor, imie in zip(dup, ["Ida", "Margarita", "Sabrina"], strict=False):
        autor.imiona = imie
        autor.save()

# 5. rebuild the slot cache (then run: manage.py denorm_flush)
for wc in Wydawnictwo_Ciagle.objects.all():
    wc.przelicz_punkty_dyscyplin()
