"""
Modele abstrakcyjne związane z miejscem przechowywania.
"""

from django.db import models


class ModelZMiejscemPrzechowywania(models.Model):
    numer_odbitki = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        abstract = True
