from collections import defaultdict
from decimal import Decimal

from ewaluacja2021.models import (
    IloscUdzialowDlaAutora_2022_2025,
    LiczbaNDlaUczelni_2022_2025,
)
from .liczba_n import Cache_Liczba_N_Last_Updated


# @transaction.atomic
def oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia, rok_min=2022, rok_max=2025):

    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina

    autor_rok_dyscyplina_na_udzial = defaultdict(lambda: defaultdict(dict))
    uczelnia_dyscyplina_udzial = defaultdict(list)

    for ad in Autor_Dyscyplina.objects.filter(rok__gte=rok_min, rok__lte=rok_max):
        for dyscyplina, slot in ad.policz_udzialy():
            autor_rok_dyscyplina_na_udzial[ad.autor_id][dyscyplina.pk][ad.rok] = slot

    for autor_id in autor_rok_dyscyplina_na_udzial:
        for dyscyplina_id in autor_rok_dyscyplina_na_udzial[autor_id]:
            latami = autor_rok_dyscyplina_na_udzial[autor_id][dyscyplina_id]

            suma = sum(latami.values())
            ilosc = len(latami.values())

            IloscUdzialowDlaAutora_2022_2025.objects.update_or_create(
                autor_id=autor_id,
                dyscyplina_naukowa_id=dyscyplina_id,
                defaults=dict(
                    ilosc_udzialow=suma, ilosc_udzialow_monografie=suma / Decimal("2.0")
                ),
            )

            uczelnia_dyscyplina_udzial[dyscyplina_id].append(suma / ilosc)

    LiczbaNDlaUczelni_2022_2025.objects.filter(uczelnia=uczelnia).delete()

    for dyscyplina_id, wartosci in uczelnia_dyscyplina_udzial.items():
        suma_srednich = sum(wartosci)

        LiczbaNDlaUczelni_2022_2025.objects.create(
            uczelnia_id=uczelnia.pk,
            dyscyplina_naukowa_id=dyscyplina_id,
            liczba_n=suma_srednich,
        )

    nie_raportowane = LiczbaNDlaUczelni_2022_2025.objects.filter(liczba_n__lt=12)

    # Dolicz +1 slot dla każdej nie-raportowanej dyscypliny
    for nie_raportowana in nie_raportowane:
        for elem in IloscUdzialowDlaAutora_2022_2025.objects.filter(
            dyscyplina_naukowa=nie_raportowana.dyscyplina_naukowa
        ):
            elem.ilosc_udzialow = min(4, elem.ilosc_udzialow + 1)
            elem.ilosc_udzialow_monografie = elem.ilosc_udzialow / Decimal("2.0")
            elem.save(update_fields=["ilosc_udzialow", "ilosc_udzialow_monografie"])

    # Usuń nie-raportowane dyscypliny z bazy
    nie_raportowane.delete()

    # Zaznacz, że policzone
    Cache_Liczba_N_Last_Updated.objects.update_or_create(
        pk=1, defaults=dict(wymaga_przeliczenia=False)
    )
