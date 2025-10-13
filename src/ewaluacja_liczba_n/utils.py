from decimal import Decimal

from django.db import transaction

from .models import (
    DyscyplinaNieRaportowana,
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni,
)


@transaction.atomic
def oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, rok_min=2022, rok_max=2025):
    """
    Oblicza średnią liczbę N dla każdej dyscypliny w przeliczeniu na pełny wymiar czasu pracy.

    Procedura:
    1. Pobiera wszystkie udziały dla autorów z tabeli IloscUdzialowDlaAutoraZaRok
    2. Łączy z danymi o wymiarze etatu z tabeli Autor_Dyscyplina
    3. Oblicza średnią arytmetyczną w przeliczeniu na pełny etat (FTE)
    4. Zapisuje wyniki do tabeli LiczbaNDlaUczelni
    """
    from collections import defaultdict

    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina

    rok_kw = dict(rok__gte=rok_min, rok__lte=rok_max)

    # Słownik do przechowywania sum udziałów i wymiarów etatu dla każdej dyscypliny
    dyscyplina_stats = defaultdict(
        lambda: {"suma_udzialow": Decimal("0"), "suma_etatow": Decimal("0")}
    )

    # Pobierz wszystkie udziały dla autorów w okresie ewaluacji
    udzialy = IloscUdzialowDlaAutoraZaRok.objects.filter(**rok_kw).select_related(
        "autor", "dyscyplina_naukowa"
    )

    # Dla każdego udziału znajdź odpowiedni wymiar etatu
    for udzial in udzialy:
        # Pobierz wymiar etatu dla autora w danym roku
        autor_dyscyplina = Autor_Dyscyplina.objects.get(
            autor=udzial.autor, rok=udzial.rok
        )

        # Tylko dla pracowników zaliczanych do liczby N
        if autor_dyscyplina.rodzaj_autora and autor_dyscyplina.rodzaj_autora.jest_w_n:

            if udzial.dyscyplina_naukowa_id == autor_dyscyplina.dyscyplina_naukowa_id:
                # Udział dotyczy DYSCYPLLINYE

                if autor_dyscyplina.wymiar_etatu is None:
                    continue

                dyscyplina_stats[udzial.dyscyplina_naukowa]["suma_etatow"] += (
                    udzial.ilosc_udzialow
                    * autor_dyscyplina.wymiar_etatu
                    * autor_dyscyplina.procent_dyscypliny
                    / Decimal("100.0")
                )

            elif (
                udzial.dyscyplina_naukowa_id
                == autor_dyscyplina.subdyscyplina_naukowa_id
            ):

                dyscyplina_stats[udzial.dyscyplina_naukowa]["suma_etatow"] += (
                    udzial.ilosc_udzialow
                    * autor_dyscyplina.wymiar_etatu
                    * autor_dyscyplina.procent_subdyscypliny
                    / Decimal("100.0")
                )

            else:
                raise NotImplementedError("Nie można policzyć -- odśwież tabelę. ")

    # Usuń istniejące rekordy dla uczelni
    LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).delete()

    # Oblicz średnią i zapisz wyniki
    liczba_lat = rok_max - rok_min + 1

    for dyscyplina, stats in dyscyplina_stats.items():
        if stats["suma_etatow"] > 0:
            # Średnia arytmetyczna w przeliczeniu na pełny wymiar czasu pracy

            srednia_calkowita = stats["suma_etatow"] / liczba_lat

            LiczbaNDlaUczelni.objects.create(
                uczelnia=uczelnia,
                dyscyplina_naukowa=dyscyplina,
                liczba_n=srednia_calkowita,
            )


@transaction.atomic
def oblicz_sumy_udzialow_za_calosc(rok_min=2022, rok_max=2025):
    """
    Oblicza sumę udziałów dla każdego autora i dyscypliny za cały okres ewaluacji.

    Args:
        rok_min: Pierwszy rok okresu ewaluacji
        rok_max: Ostatni rok okresu ewaluacji
    """
    from django.db.models import Sum

    # Wyczyść istniejące dane
    IloscUdzialowDlaAutoraZaCalosc.objects.all().delete()

    # Agreguj dane z tabeli rocznej
    sumy = (
        IloscUdzialowDlaAutoraZaRok.objects.filter(rok__gte=rok_min, rok__lte=rok_max)
        .values("autor", "dyscyplina_naukowa")
        .annotate(
            suma_udzialow=Sum("ilosc_udzialow"),
            suma_monografie=Sum("ilosc_udzialow_monografie"),
        )
    )

    # Zapisz zagregowane dane
    for suma in sumy:
        lata_z_danymi = (
            IloscUdzialowDlaAutoraZaRok.objects.filter(
                autor_id=suma["autor"],
                dyscyplina_naukowa_id=suma["dyscyplina_naukowa"],
                rok__gte=rok_min,
                rok__lte=rok_max,
            )
            .values_list("rok", flat=True)
            .order_by("rok")
        )

        # Pobierz dane o rodzaju autora dla każdego roku
        from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina

        rodzaje_autora_rocznie = {}
        for rok in lata_z_danymi:
            try:
                autor_dyscyplina = Autor_Dyscyplina.objects.get(
                    autor_id=suma["autor"], rok=rok
                )
                if autor_dyscyplina.rodzaj_autora:
                    rodzaje_autora_rocznie[rok] = autor_dyscyplina.rodzaj_autora.nazwa
            except Autor_Dyscyplina.DoesNotExist:
                pass

        # Zbuduj komentarz z informacjami o rodzaju autora
        komentarz = f"Lata z danymi: {', '.join(map(str, lata_z_danymi))}"

        if rodzaje_autora_rocznie:
            unikalne_rodzaje = set(rodzaje_autora_rocznie.values())
            if len(unikalne_rodzaje) == 1:
                # Tylko jeden rodzaj autora przez wszystkie lata
                komentarz += f" | rodzaj autora: {list(unikalne_rodzaje)[0]}"
            else:
                # Wiele rodzajów autora w różnych latach
                rodzaje_parts = []
                for rok in sorted(rodzaje_autora_rocznie.keys()):
                    rodzaje_parts.append(f"{rok} - {rodzaje_autora_rocznie[rok]}")
                komentarz += f" | rodzaj autora: {', '.join(rodzaje_parts)}"

        # Zastosuj minimalną wartość 1 jeśli suma jest mniejsza niż 1
        suma_udzialow_final = suma["suma_udzialow"]
        suma_monografie_final = suma["suma_monografie"]

        if suma_udzialow_final > 0 and suma_udzialow_final < 1:
            komentarz += (
                f" | Ilość udziałów zaokrąglona: {suma_udzialow_final:.4f} → 1.00"
            )
            suma_udzialow_final = Decimal("1")

        if suma_monografie_final > 0 and suma_monografie_final < 1:
            komentarz += f" | Ilość udziałów za monografie zaokrąglona: {suma_monografie_final:.4f} → 1.00"
            suma_monografie_final = Decimal("1")

        IloscUdzialowDlaAutoraZaCalosc.objects.create(
            autor_id=suma["autor"],
            dyscyplina_naukowa_id=suma["dyscyplina_naukowa"],
            ilosc_udzialow=suma_udzialow_final,
            ilosc_udzialow_monografie=suma_monografie_final,
            komentarz=komentarz,
        )


@transaction.atomic
def identyfikuj_dyscypliny_nieraportowane(uczelnia, prog_liczby_n=12):
    """
    Identyfikuje dyscypliny nieraportowane zgodnie z rozporządzeniem.

    Dyscypliny z liczbą N < 12 są uznawane za nieraportowane w ewaluacji.

    Args:
        uczelnia: Instancja modelu Uczelnia
        prog_liczby_n: Minimalna liczba N wymagana do raportowania (domyślnie 12)
    """
    # Wyczyść istniejące wpisy dla uczelni
    DyscyplinaNieRaportowana.objects.filter(uczelnia=uczelnia).delete()

    # Znajdź dyscypliny z liczbą N poniżej progu
    dyscypliny_ponizej_progu = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__lt=prog_liczby_n
    ).select_related("dyscyplina_naukowa")

    # Zapisz dyscypliny nieraportowane wraz z ich liczbą N
    for liczba_n_obj in dyscypliny_ponizej_progu:
        DyscyplinaNieRaportowana.objects.create(
            uczelnia=uczelnia,
            dyscyplina_naukowa=liczba_n_obj.dyscyplina_naukowa,
            liczba_n=liczba_n_obj.liczba_n,
        )

    # Usuń dyscypliny nieraportowane z LiczbaNDlaUczelni
    # (nie są uwzględniane w oficjalnej liczbie N uczelni)
    dyscypliny_ponizej_progu.delete()

    return DyscyplinaNieRaportowana.objects.filter(uczelnia=uczelnia).count()


@transaction.atomic
def oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia, rok_min=2022, rok_max=2025):
    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina

    warunek_lat = dict(rok__gte=rok_min, rok__lte=rok_max)

    IloscUdzialowDlaAutoraZaRok.objects.filter(**warunek_lat).delete()

    wymiary_etatu = []

    for ad in Autor_Dyscyplina.objects.filter(**warunek_lat):
        if ad.wymiar_etatu is not None:
            wymiary_etatu.append(ad.wymiar_etatu)

        for dyscyplina, ilosc_udzialow in ad.policz_udzialy():
            IloscUdzialowDlaAutoraZaRok.objects.create(
                rok=ad.rok,
                autor=ad.autor,
                dyscyplina_naukowa=dyscyplina,
                ilosc_udzialow=ilosc_udzialow,
                ilosc_udzialow_monografie=ilosc_udzialow
                / Decimal("2.0"),  # Domyślnie połowa udziałów
            )

    # Oblicz sumę udziałów dla całego okresu ewaluacji
    oblicz_sumy_udzialow_za_calosc(rok_min, rok_max)

    # Policz średnią dla dyscyplin
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, rok_min, rok_max)

    # Identyfikuj i zapisz dyscypliny nieraportowane zgodnie z rozporządzeniem
    liczba_nieraportowanych = identyfikuj_dyscypliny_nieraportowane(uczelnia)  # noqa

    #         # Jeżeli suma udziałów za 4 lata jest mniejsza jak 1 i jest włączona odpowiednia flaga
    #         # to zwiększ do 1 slota:
    #         if uczelnia.przydzielaj_1_slot_gdy_udzial_mniejszy:
    #             suma = max(1, suma)
    #             suma_monografie = max(1, suma_monografie)
    #
    #         suma = min(4, suma)
    #         suma_monografie = min(4, suma)
    #
    #         IloscUdzialowDlaAutoraZaRok.objects.update_or_create(
    #             autor_id=autor_id,
    #             dyscyplina_naukowa_id=dyscyplina_id,
    #             defaults=dict(
    #                 ilosc_udzialow=suma, ilosc_udzialow_monografie=suma_monografie
    #             ),
    #         )
    #
    #         suma_dla_uczelni = 0
    #         if rodzaj_autora == Autor_Dyscyplina.RODZAJE_AUTORA.N:
    #             suma_dla_uczelni = suma
    #
    #         # Zawsze na 4 lata:
    #         ilosc = Decimal(4)  # len(latami.values())
    #         uczelnia_dyscyplina_udzial[dyscyplina_id].append(suma_dla_uczelni / ilosc)
    #
    # LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).delete()
    #
    # for dyscyplina_id, wartosci in uczelnia_dyscyplina_udzial.items():
    #     suma_srednich = sum(wartosci)
    #
    #     LiczbaNDlaUczelni.objects.create(
    #         uczelnia_id=uczelnia.pk,
    #         dyscyplina_naukowa_id=dyscyplina_id,
    #         liczba_n=suma_srednich,
    #     )
    #
    # # Policz dyscypliny za ostatni rok ewaluacji które mają < 12 slotów:
    # nie_raportowane = (
    #     IloscUdzialowDlaAutoraZaRok.objects.filter(rok=2025)
    #     .values("dyscyplina_naukowa")
    #     .annotate(Sum("ilosc_udzialow"))
    #     .filter(ilosc_udzialow__sum__lt=12)
    # )
    #
    # DyscyplinaNieRaportowana.objects.filter(uczelnia=uczelnia).delete()
    #
    # # Dolicz +1 slot dla każdej nie-raportowanej dyscypliny
    # for nie_raportowana in nie_raportowane:
    #     DyscyplinaNieRaportowana.objects.get_or_create(
    #         uczelnia=uczelnia,
    #         dyscyplina_naukowa_id=nie_raportowana["dyscyplina_naukowa"],
    #     )
    #
    #     for elem in IloscUdzialowDlaAutoraZaRok.objects.filter(
    #         dyscyplina_naukowa_id=nie_raportowana["dyscyplina_naukowa"]
    #     ):
    #         elem.ilosc_udzialow = min(4, elem.ilosc_udzialow + 1)
    #         elem.ilosc_udzialow_monografie = elem.ilosc_udzialow / Decimal("2.0")
    #         elem.save(update_fields=["ilosc_udzialow", "ilosc_udzialow_monografie"])
    #
    # # Usuń liczby N za nie-raportowane dyscypliny z bazy
    # for dyscyplina_nie_raportowana in DyscyplinaNieRaportowana.objects.filter(
    #     uczelnia=uczelnia
    # ):
    #     IloscUdzialowDlaAutoraZaRok.objects.filter(
    #         dyscyplina_naukowa=dyscyplina_nie_raportowana.dyscyplina_naukowa
    #     ).delete()
    #
    #     IloscUdzialowDlaAutoraZaRok.objects.filter(
    #         dyscyplina_naukowa=dyscyplina_nie_raportowana.dyscyplina_naukowa
    #     ).delete()
    #
    # # Zaznacz, że policzone
    # Cache_Liczba_N_Last_Updated.objects.update_or_create(
    #     pk=1, defaults=dict(wymaga_przeliczenia=False)
    # )
