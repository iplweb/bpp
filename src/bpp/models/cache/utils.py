from collections import defaultdict
from decimal import Decimal

from ewaluacja2021.models import (
    IloscUdzialowDlaAutora_2022_2025,
    IloscUdzialowDlaAutoraZaRok,
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
            autor_rok_dyscyplina_na_udzial[ad.autor_id][dyscyplina.pk][ad.rok] = (
                slot,
                ad.rodzaj_autora,
            )

    for autor_id in autor_rok_dyscyplina_na_udzial:
        for dyscyplina_id in autor_rok_dyscyplina_na_udzial[autor_id]:
            latami = autor_rok_dyscyplina_na_udzial[autor_id][dyscyplina_id]

            # Wrzuć do bazy ilość udziałów za kazdy rok

            for rok, (slot, rodzaj_autora) in latami.items():
                IloscUdzialowDlaAutoraZaRok.objects.update_or_create(
                    autor_id=autor_id,
                    rok=rok,
                    dyscyplina_naukowa_id=dyscyplina_id,
                    defaults=dict(
                        ilosc_udzialow=slot,
                        ilosc_udzialow_monografie=slot / Decimal("2.0"),
                    ),
                )

            # Jeżeli suma udziałów za 4 lata jest mniejsza jak 1, to zwiększ do 1 slota:
            suma = max(1, sum(slot for slot, rodzaj_autora in latami.values()))
            suma_monografie = max(1, suma / Decimal("2.0"))

            IloscUdzialowDlaAutora_2022_2025.objects.update_or_create(
                autor_id=autor_id,
                dyscyplina_naukowa_id=dyscyplina_id,
                defaults=dict(
                    ilosc_udzialow=suma, ilosc_udzialow_monografie=suma_monografie
                ),
            )

            suma_dla_uczelni = 0
            if rodzaj_autora == Autor_Dyscyplina.RODZAJE_AUTORA.N:
                # Bierz ZAOKRĄGLONĄ sumę udziałów jako sumę dla uczelni
                suma_dla_uczelni = suma

            # Zawsze na 4 lata:
            ilosc = Decimal(4)  # len(latami.values())

            uczelnia_dyscyplina_udzial[dyscyplina_id].append(suma_dla_uczelni / ilosc)

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
