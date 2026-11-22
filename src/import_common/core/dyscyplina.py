"""Matchowanie dyscyplin naukowych: zarówno wewnętrznych
(`bpp.Dyscyplina_Naukowa`), jak i tych z PBN (`pbn_api.Discipline`).
"""

from datetime import date

from django.db.models import Q

from bpp.models import Dyscyplina_Naukowa

from ..normalization import normalize_kod_dyscypliny, normalize_nazwa_dyscypliny

# Dzień, na który wybieramy słownik dyscyplin PBN dla okresu ewaluacyjnego
# w Tłumaczu Dyscyplin (``pbn_api.TlumaczDyscyplin``): słownik obowiązujący
# w tym dniu tłumaczy dyscypliny rekordów z tego okresu. Słowniki PBN mają daty
# graniczne w trakcie roku (2018-01-01 – 2022-11-10, 2022-11-11 – 2023-10-05,
# od 2023-10-06), więc wybór po samej parze lat jest kruchy (FD#608). Dni leżą
# w środku okresów, z dala od dat granicznych. Okres 2024+ bierze słownik
# obowiązujący dziś (``matchuj_aktualna_dyscypline_pbn``).
DZIEN_SLOWNIKA_PBN_2017_2021 = date(2020, 1, 1)
DZIEN_SLOWNIKA_PBN_2022_2023 = date(2023, 1, 1)


def matchuj_dyscypline(kod, nazwa):
    if nazwa:
        for nazwa_kandydat in [nazwa, nazwa.split("(", 2)[0]]:
            nazwa_znormalizowana = normalize_nazwa_dyscypliny(nazwa_kandydat)
            try:
                return Dyscyplina_Naukowa.objects.get(nazwa=nazwa_znormalizowana)
            except Dyscyplina_Naukowa.DoesNotExist:
                pass
            except Dyscyplina_Naukowa.MultipleObjectsReturned:
                pass

    if kod:
        kod = normalize_kod_dyscypliny(kod)
        try:
            return Dyscyplina_Naukowa.objects.get(kod=kod)
        except Dyscyplina_Naukowa.DoesNotExist:
            pass
        except Dyscyplina_Naukowa.MultipleObjectsReturned:
            pass


def normalize_kod_dyscypliny_pbn(kod):
    if kod is None:
        raise ValueError("kod = None")

    if kod.find(".") == -1:
        # Nie ma kropki, wiec juz znormalizowany
        return kod

    k1, k2 = (int(x) for x in kod.split(".", 2))
    return f"{k1}{k2:02}"


def matchuj_dyscypline_pbn_na_dzien(kod, nazwa, dzien):
    """Dyscyplina PBN ze słownika obowiązującego w dniu ``dzien``.

    Słownik wybieramy po tym, czy jego zakres ważności obejmuje ``dzien``
    (obie granice włącznie, ``validityDateTo=None`` = bez końca), a nie po
    latach początku/końca zakresu. PBN przesuwa daty graniczne słowników
    (np. 2022-11-10 / 2022-11-11, 2023-10-05 / 2023-10-06), więc warunek
    „zaczyna się w roku X, kończy w roku Y” potrafi nie trafić w żaden słownik
    (FD#608). Gdy zakresy się nakładają, wygrywa słownik zaczynający się
    najpóźniej.

    Najpierw szuka po kodzie, potem po nazwie. Zwraca ``None``, gdy nic nie
    pasuje (np. brak słownika na ten dzień w lokalnej bazie).
    """
    kod = normalize_kod_dyscypliny_pbn(kod)

    from pbn_api.models import Discipline

    kandydaci = Discipline.objects.filter(
        Q(parent_group__validityDateFrom__lte=dzien),
        Q(parent_group__validityDateTo=None)
        | Q(parent_group__validityDateTo__gte=dzien),
    ).order_by("-parent_group__validityDateFrom", "pk")

    for warunek in (Q(code=kod), Q(name=nazwa)):
        znaleziona = kandydaci.filter(warunek).first()
        if znaleziona is not None:
            return znaleziona
    return None


def matchuj_aktualna_dyscypline_pbn(kod, nazwa):
    from django.utils import timezone

    return matchuj_dyscypline_pbn_na_dzien(kod, nazwa, timezone.now().date())
