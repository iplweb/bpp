"""Apka ``ewaluacja2021`` jest wygaszona — patrz ``README.md``.

Modele zostały usunięte (migracja 0020 zdejmuje tabele z bazy). Pozostaje tu
jedynie funkcja ``dyscypliny_naukowe_w_bazie``, bo historyczna migracja
``0007_auto_20211110_0002`` odwołuje się do niej w ``limit_choices_to`` i musi
być importowalna przy każdym ``migrate``. NIE dodawać tu nowych modeli.
"""

from bpp.models import Cache_Punktacja_Autora_Query


def dyscypliny_naukowe_w_bazie():
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    dyscypliny_z_liczba_n = LiczbaNDlaUczelni.objects.values_list(
        "dyscyplina_naukowa", flat=True
    )

    return {
        "pk__in": [
            dyscyplina
            for dyscyplina in Cache_Punktacja_Autora_Query.objects.values_list(
                "dyscyplina", flat=True
            ).distinct()
            if dyscyplina in dyscypliny_z_liczba_n
        ]
    }
