"""FD#608: uzupełnia puste pola Tłumacza Dyscyplin z lokalnych słowników PBN.

Synchronizacja dyscyplin z PBN szukała słownika 2022-2023 warunkiem „zaczyna
się w 2023, kończy w 2024”, w który nie trafia żaden słownik PBN (realne
zakresy: 2018-01-01 – 2022-11-10, 2022-11-11 – 2023-10-05, od 2023-10-06).
Każdy import z PBN zerował więc ``pbn_2022_2023`` i wysyłka publikacji z lat
2022-2023 z dyscypliną kończyła się ``TlumaczDyscyplinException``.

Migracja NIE łączy się z PBN: dopasowuje dyscypliny ze słowników już
zapisanych w bazie, wybierając słownik obowiązujący w dniu z danego okresu
(jak poprawiony kod synchronizacji). Uzupełnia WYŁĄCZNIE puste pola — wpisy
istniejące (także ręczne) zostają. Idempotentna; bez słowników w bazie (świeża
instalacja) nic nie robi. Cofnięcie = brak operacji.

Logika jest celowo skopiowana (a nie importowana z ``import_common``), żeby
migracja działała na modelach historycznych niezależnie od przyszłych zmian
kodu aplikacji.
"""

from datetime import date

from django.db import migrations
from django.db.models import Q
from django.utils import timezone

# Kopie ``DZIEN_SLOWNIKA_PBN_*`` z ``import_common.core.dyscyplina``.
DZIEN_2017_2021 = date(2020, 1, 1)
DZIEN_2022_2023 = date(2023, 1, 1)


def _kod_pbn(kod):
    if not kod or "." not in kod:
        return kod
    k1, k2 = (int(x) for x in kod.split(".", 1))
    return f"{k1}{k2:02}"


def _dyscyplina_na_dzien(Discipline, kod, nazwa, dzien):
    kandydaci = Discipline.objects.filter(
        Q(parent_group__validityDateFrom__lte=dzien),
        Q(parent_group__validityDateTo=None)
        | Q(parent_group__validityDateTo__gte=dzien),
    ).order_by("-parent_group__validityDateFrom", "pk")

    for pole, wartosc in (("code", _kod_pbn(kod)), ("name", nazwa)):
        if not wartosc:
            continue
        znaleziona = kandydaci.filter(**{pole: wartosc}).first()
        if znaleziona is not None:
            return znaleziona
    return None


def uzupelnij_tlumacza(apps, schema_editor):
    Discipline = apps.get_model("pbn_api", "Discipline")
    TlumaczDyscyplin = apps.get_model("pbn_api", "TlumaczDyscyplin")

    if not Discipline.objects.exists():
        return

    dni = (
        ("pbn_2017_2021", DZIEN_2017_2021),
        ("pbn_2022_2023", DZIEN_2022_2023),
        ("pbn_2024_now", timezone.now().date()),
    )

    for wpis in TlumaczDyscyplin.objects.select_related("dyscyplina_w_bpp"):
        dyscyplina = wpis.dyscyplina_w_bpp
        zmienione = []
        for pole, dzien in dni:
            if getattr(wpis, f"{pole}_id") is not None:
                continue
            znaleziona = _dyscyplina_na_dzien(
                Discipline, dyscyplina.kod, dyscyplina.nazwa, dzien
            )
            if znaleziona is not None:
                setattr(wpis, pole, znaleziona)
                zmienione.append(pole)
        if zmienione:
            wpis.save(update_fields=zmienione)


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_api", "0080_sentdata_withdrawn_at"),
    ]

    operations = [
        migrations.RunPython(uzupelnij_tlumacza, migrations.RunPython.noop),
    ]
