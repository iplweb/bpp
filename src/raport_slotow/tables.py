
import django_tables2 as tables
from django_tables2 import Column

from bpp.models.cache import Cache_Punktacja_Autora_Query

class Cache_Punktacja_Autora_QueryTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = ("tytul_oryginalny",
                  "autorzy",
                  "zrodlo",
                  "dyscyplina",
                  "pkdaut",
                  "slot")

    tytul_oryginalny = Column("Tytuł oryginalny", "rekord.tytul_oryginalny")
    autorzy = Column("Autorzy", "rekord.opis_bibliograficzny_zapisani_autorzy_cache", orderable=False)
    zrodlo = Column("Źródło", "rekord.zrodlo")
    pkdaut = Column("PKdAut", "pkdaut")

