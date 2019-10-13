import django_tables2 as tables
from django.template.defaultfilters import safe
from django.urls import reverse
from django_tables2 import Column

from bpp.models.cache import Cache_Punktacja_Autora_Query
from raport_slotow.columns import DecimalColumn, SummingColumn


class RaportSlotowAutorTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = ("tytul_oryginalny",
                  "autorzy",
                  "rok",
                  "zrodlo",
                  "dyscyplina",
                  "pkdaut",
                  "slot")

    tytul_oryginalny = Column("Tytuł oryginalny", "rekord.tytul_oryginalny")
    autorzy = Column("Autorzy", "rekord.opis_bibliograficzny_zapisani_autorzy_cache", orderable=False)
    rok = Column("Rok", "rekord.rok", orderable=True)
    dyscyplina = Column(orderable=False)
    zrodlo = Column("Źródło", "rekord.zrodlo", empty_values=())
    pkdaut = SummingColumn("PKdAut", "pkdaut")
    slot = SummingColumn("Slot")

    def render_tytul_oryginalny(self, value):
        return safe(value)

    def render_zrodlo(self, value):
        if value is None:
            return "-"
        return value



class RaportSlotowUczelniaTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = ("autor",
                  "dyscyplina",
                  "pkdautsum",
                  "pkdautslotsum",
                  "avg")

    pkdautsum = DecimalColumn("Suma PKd Aut")
    pkdautslotsum = DecimalColumn("Slot")
    avg = Column("Średnio PKd na slot")
    dyscyplina = Column()

    def __init__(self, od_roku, do_roku, *args, **kw):
        self.od_roku = od_roku
        self.do_roku = do_roku
        super(RaportSlotowUczelniaTable, self).__init__(*args, **kw)

    def render_avg(self, value):
        return round(value, 4)

    # def value_avg(self, value):
    #     return round(value, 4)

    def render_autor(self, value):
        url = reverse("raport_slotow:raport", args=(value.slug, self.od_roku, self.do_roku))
        return safe("<a href=%s>%s</a>" % (url, value))

    def value_autor(self, value):
        return value
