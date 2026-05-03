"""Matchowanie dyscyplin naukowych: zarówno wewnętrznych
(`bpp.Dyscyplina_Naukowa`), jak i tych z PBN (`pbn_api.Discipline`).
"""

from django.db.models import Q

from bpp.models import Dyscyplina_Naukowa

from ..normalization import normalize_kod_dyscypliny, normalize_nazwa_dyscypliny


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


def matchuj_aktualna_dyscypline_pbn(kod, nazwa):
    kod = normalize_kod_dyscypliny_pbn(kod)

    from django.utils import timezone

    from pbn_api.models import Discipline

    d = timezone.now().date()
    parent_group_args = (
        Q(parent_group__validityDateFrom__lte=d),
        Q(parent_group__validityDateTo=None) | Q(parent_group__validityDateTo__gt=d),
    )

    try:
        return Discipline.objects.get(*parent_group_args, code=kod)
    except Discipline.DoesNotExist:
        pass

    try:
        return Discipline.objects.get(*parent_group_args, name=nazwa)
    except Discipline.DoesNotExist:
        pass


def matchuj_nieaktualna_dyscypline_pbn(kod, nazwa, rok_min=2018, rok_max=2022):
    kod = normalize_kod_dyscypliny_pbn(kod)

    from pbn_api.models import Discipline

    nieaktualna_parent_group_args = (
        Q(parent_group__validityDateFrom__year=rok_min),
        Q(parent_group__validityDateTo__year=rok_max),
    )
    try:
        return Discipline.objects.get(*nieaktualna_parent_group_args, code=kod)
    except Discipline.DoesNotExist:
        pass

    try:
        return Discipline.objects.get(*nieaktualna_parent_group_args, name=nazwa)
    except Discipline.DoesNotExist:
        pass
