from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from .models import (
    DyscyplinaNieRaportowana_2022_2025,
    IloscUdzialowDlaAutora_2022_2025,
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni_2022_2025,
)

from bpp.models.cache.liczba_n import Cache_Liczba_N_Last_Updated


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

            suma = sum(slot for slot, rodzaj_autora in latami.values())
            suma_monografie = suma / Decimal("2.0")

            # Jeżeli suma udziałów za 4 lata jest mniejsza jak 1 i jest włączona odpowiednia flaga
            # to zwiększ do 1 slota:
            if uczelnia.przydzielaj_1_slot_gdy_udzial_mniejszy:
                suma = max(1, suma)
                suma_monografie = max(1, suma_monografie)

            suma = min(4, suma)
            suma_monografie = min(4, suma)

            IloscUdzialowDlaAutora_2022_2025.objects.update_or_create(
                autor_id=autor_id,
                dyscyplina_naukowa_id=dyscyplina_id,
                defaults=dict(
                    ilosc_udzialow=suma, ilosc_udzialow_monografie=suma_monografie
                ),
            )

            suma_dla_uczelni = 0
            if rodzaj_autora == Autor_Dyscyplina.RODZAJE_AUTORA.N:
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

    # Policz dyscypliny za ostatni rok ewaluacji które mają < 12 slotów:
    nie_raportowane = (
        IloscUdzialowDlaAutoraZaRok.objects.filter(rok=2025)
        .values("dyscyplina_naukowa")
        .annotate(Sum("ilosc_udzialow"))
        .filter(ilosc_udzialow__sum__lt=12)
    )

    DyscyplinaNieRaportowana_2022_2025.objects.filter(uczelnia=uczelnia).delete()

    # Dolicz +1 slot dla każdej nie-raportowanej dyscypliny
    for nie_raportowana in nie_raportowane:
        DyscyplinaNieRaportowana_2022_2025.objects.get_or_create(
            uczelnia=uczelnia,
            dyscyplina_naukowa_id=nie_raportowana["dyscyplina_naukowa"],
        )

        for elem in IloscUdzialowDlaAutora_2022_2025.objects.filter(
            dyscyplina_naukowa_id=nie_raportowana["dyscyplina_naukowa"]
        ):
            elem.ilosc_udzialow = min(4, elem.ilosc_udzialow + 1)
            elem.ilosc_udzialow_monografie = elem.ilosc_udzialow / Decimal("2.0")
            elem.save(update_fields=["ilosc_udzialow", "ilosc_udzialow_monografie"])

    # Usuń liczby N za nie-raportowane dyscypliny z bazy
    for dyscyplina_nie_raportowana in DyscyplinaNieRaportowana_2022_2025.objects.filter(
        uczelnia=uczelnia
    ):
        IloscUdzialowDlaAutora_2022_2025.objects.filter(
            dyscyplina_naukowa=dyscyplina_nie_raportowana.dyscyplina_naukowa
        ).delete()

        IloscUdzialowDlaAutoraZaRok.objects.filter(
            dyscyplina_naukowa=dyscyplina_nie_raportowana.dyscyplina_naukowa
        ).delete()

    # Zaznacz, że policzone
    Cache_Liczba_N_Last_Updated.objects.update_or_create(
        pk=1, defaults=dict(wymaga_przeliczenia=False)
    )
