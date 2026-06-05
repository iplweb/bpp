"""
Modele abstrakcyjne związane z tytułami w wielu językach.
"""

from django.db import models


class BazaModeluTytulow(models.Model):
    """Tytuł rekordu w jednym (dodatkowym) języku.

    Tytuł oryginalny i przetłumaczony siedzą bezpośrednio na rekordzie w polach
    ``tytul_oryginalny`` i ``tytul`` (patrz: ``DwaTytuly``). Tu trzymamy tytuły w
    POZOSTAŁYCH językach (np. niemiecki, rosyjski, litewski) — analogicznie do
    streszczeń (``BazaModeluStreszczen``), po jednym wierszu na język.

    ``kod_jezyka_pbn`` zachowuje surowy kod języka z PBN nawet wtedy, gdy danego
    języka nie ma w słowniku ``Jezyk`` (wówczas ``jezyk`` zostaje pusty) — dzięki
    temu nic nie ginie i da się to później poprawić ręcznie.
    """

    jezyk = models.ForeignKey(
        "bpp.Jezyk", null=True, blank=True, on_delete=models.SET_NULL
    )
    kod_jezyka_pbn = models.CharField(
        "Kod języka wg PBN", max_length=5, blank=True, default=""
    )
    tytul = models.TextField("Tytuł", blank=True, default="")

    class Meta:
        abstract = True
