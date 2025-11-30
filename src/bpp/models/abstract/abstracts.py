"""
Modele abstrakcyjne związane ze streszczeniami.
"""

from django.db import models


class BazaModeluStreszczen(models.Model):
    jezyk_streszczenia = models.ForeignKey(
        "bpp.Jezyk", null=True, blank=True, on_delete=models.SET_NULL
    )
    streszczenie = models.TextField(blank=True, default="")

    class Meta:
        abstract = True
