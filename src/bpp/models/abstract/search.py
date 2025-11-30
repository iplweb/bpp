"""
Modele abstrakcyjne związane z wyszukiwaniem i danymi legacy.
"""

from django.contrib.postgres.fields import HStoreField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.db import models


class ModelPrzeszukiwalny(models.Model):
    """Model zawierający pole pełnotekstowego przeszukiwania
    'search_index'"""

    search_index = VectorField()
    tytul_oryginalny_sort = models.TextField(db_index=True, default="")

    class Meta:
        abstract = True


class ModelZLegacyData(models.Model):
    """Model zawierający informacje zaimportowane z poprzedniego systemu,
    nie mające odpowiednika w nowych danych, jednakże pozostawione na
    rekordzie w taki sposób, aby w razie potrzeby w przyszłości można było
    z nich skorzystać"""

    legacy_data = HStoreField(blank=True, null=True)

    class Meta:
        abstract = True
