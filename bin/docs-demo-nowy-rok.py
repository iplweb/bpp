"""Stan demo do zrzutów docs/redaktor/nowy-rok.md (scenariusz ``nowy-rok``).

Uruchom na bazie demo (docs/deweloper/zrzuty-ekranu.md) PO
bin/docs-demo-import-list-ministerialnych.py (nadaje czasopismu ISSN
„Folii Temerskiej”):

    uv run python src/manage.py shell < bin/docs-demo-nowy-rok.py

Strona opisuje „styczeń, nowy rok jeszcze bez danych”. Skrypt:

- dopisuje autorce konta ``yennefer`` brakujące przypisania do dyscypliny na
  lata 2020-2026 (z dyscypliną z ostatniego roku), bez roku 2027,
- „Folii Temerskiej” (po ISSN) uzupełnia punktację i dyscypliny na lata
  2024-2026 (wzorem najnowszego roku), bez roku 2027,
- tworzy artykuł z 2027 r. w tym czasopiśmie, z Yennefer jako pierwszą
  autorką (tytuł: ``TYTUL_PRACY_2027`` w bpp.demo_data.zrzuty — po nim
  scenariusz znajduje pracę).

Obiekty wybiera bpp.demo_data.zrzuty, wspólnie ze scenariuszem. Ponowne
uruchomienie daje ten sam stan.
"""

from decimal import Decimal

from django.db import transaction

from bpp.demo_data import zrzuty
from bpp.models import (
    Autor_Dyscyplina,
    Charakter_Formalny,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Wydawnictwo_Ciagle,
)
from ewaluacja_common.models import Rodzaj_Autora

LATA = range(2020, 2027)
NOWY_ROK = 2027

with transaction.atomic():
    yen = zrzuty.yennefer()
    jednostka = zrzuty.aktualna_jednostka(yen)
    folia = zrzuty.zrodlo_po_issn(zrzuty.ISSN_FOLIA_TEMERSKA)

    # --- autorka: dyscypliny 2020-2026, bez 2027 -------------------------
    Autor_Dyscyplina.objects.filter(autor=yen, rok__gte=NOWY_ROK).delete()
    wzor = Autor_Dyscyplina.objects.filter(autor=yen).order_by("-rok").first()
    if wzor is None:
        zrzuty.brak("przypisanie Yennefer do dyscypliny (bin/docs-demo-sloty.py)")
    for rok in LATA:
        Autor_Dyscyplina.objects.get_or_create(
            autor=yen,
            rok=rok,
            defaults=dict(
                dyscyplina_naukowa=wzor.dyscyplina_naukowa,
                rodzaj_autora=wzor.rodzaj_autora
                or Rodzaj_Autora.objects.get(skrot="N"),
                wymiar_etatu=wzor.wymiar_etatu,
                procent_dyscypliny=wzor.procent_dyscypliny,
            ),
        )

    # --- czasopismo: punktacja i dyscypliny 2024-2026, bez 2027 ----------
    folia.punktacja_zrodla_set.filter(rok__gte=NOWY_ROK).delete()
    folia.dyscyplina_zrodla_set.filter(rok__gte=NOWY_ROK).delete()
    pz = folia.punktacja_zrodla_set.order_by("-rok").first()
    punkty = pz.punkty_kbn if pz else Decimal("40")
    ostatni = folia.dyscyplina_zrodla_set.order_by("-rok").values_list("rok", flat=True)
    dyscypliny = (
        list(
            folia.dyscyplina_zrodla_set.filter(rok=ostatni[0]).values_list(
                "dyscyplina", flat=True
            )
        )
        if ostatni
        else []
    )
    if not dyscypliny:
        zrzuty.brak(
            "dyscypliny Folii Temerskiej (bin/docs-demo-import-list-ministerialnych.py)"
        )
    for rok in range(2024, NOWY_ROK):
        Punktacja_Zrodla.objects.get_or_create(
            zrodlo=folia, rok=rok, defaults=dict(punkty_kbn=punkty)
        )
        for d in dyscypliny:
            Dyscyplina_Zrodla.objects.get_or_create(
                zrodlo=folia, rok=rok, dyscyplina_id=d
            )

    # --- artykuł z 2027 r. ------------------------------------------------
    Wydawnictwo_Ciagle.objects.filter(tytul_oryginalny=zrzuty.TYTUL_PRACY_2027).delete()
    wzor_pracy = (
        Wydawnictwo_Ciagle.objects.filter(zrodlo=folia).order_by("-rok", "pk").first()
    )
    if wzor_pracy is None:
        zrzuty.brak("praca w Folii Temerskiej")
    praca = Wydawnictwo_Ciagle.objects.create(
        tytul_oryginalny=zrzuty.TYTUL_PRACY_2027,
        rok=NOWY_ROK,
        zrodlo=folia,
        charakter_formalny=Charakter_Formalny.objects.get(skrot="AC"),
        typ_kbn=wzor_pracy.typ_kbn,
        jezyk=wzor_pracy.jezyk,
        status_korekty=wzor_pracy.status_korekty,
        szczegoly="s. 1-12",
    )
    praca.dodaj_autora(yen, jednostka)

print(
    f"nowy-rok: {yen} — dyscypliny {LATA.start}-{LATA.stop - 1}; "
    f"{folia.nazwa} — punktacja do {NOWY_ROK - 1}; praca 2027: pk {praca.pk}"
)
