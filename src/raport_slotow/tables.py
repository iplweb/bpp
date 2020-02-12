import django_tables2 as tables
from django.template.defaultfilters import safe
from django.urls import reverse
from django_tables2 import Column

from bpp.models.cache import Cache_Punktacja_Autora_Query
from raport_slotow.columns import DecimalColumn, SummingColumn
from raport_slotow.models import RaportZerowyEntry


class RaportSlotowAutorTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = (
            "tytul_oryginalny",
            "autorzy",
            "rok",
            "zrodlo",
            "dyscyplina",
            "punkty_kbn",
            "pkdaut",
            "slot",
        )

    tytul_oryginalny = Column("Tytuł oryginalny", "rekord")
    autorzy = Column(
        "Autorzy", "rekord.opis_bibliograficzny_zapisani_autorzy_cache", orderable=False
    )
    rok = Column("Rok", "rekord.rok", orderable=True)
    dyscyplina = Column(orderable=False)
    punkty_kbn = Column("Punkty PK", "rekord.punkty_kbn")
    zrodlo = Column("Źródło", "rekord.zrodlo", empty_values=())
    pkdaut = SummingColumn("Punkty dla autora", "pkdaut")
    slot = SummingColumn("Slot")

    def render_tytul_oryginalny(self, value):
        url = reverse("bpp:browse_rekord", args=(value.pk[0], value.pk[1]))
        return safe("<a href=%s>%s</a>" % (url, value))

    def value_tytul_oryginalny(self, value):
        return value.tytul_oryginalny

    def render_zrodlo(self, value):
        if value is None:
            return "-"
        return value


class RaportSlotowUczelniaTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = (
            "autor",
            "jednostka",
            "wydzial",
            "dyscyplina",
            "pkdautsum",
            "pkdautslotsum",
            "avg",
        )

    pkdautsum = DecimalColumn("Suma punktów dla autora")
    pkdautslotsum = DecimalColumn("Slot")
    avg = Column("Średnio punktów dla autora na slot")
    wydzial = Column("Wydział", accessor="jednostka.wydzial.nazwa")
    dyscyplina = Column()

    def __init__(self, od_roku, do_roku, *args, **kw):
        self.od_roku = od_roku
        self.do_roku = do_roku
        super(RaportSlotowUczelniaTable, self).__init__(*args, **kw)

    def render_avg(self, value):
        return round(value, 4)

    def render_autor(self, value):
        url = reverse(
            "raport_slotow:raport", args=(value.slug, self.od_roku, self.do_roku)
        )
        return safe("<a href=%s>%s</a>" % (url, value))

    def value_autor(self, value):
        return value


class RaportSlotowZerowyTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = RaportZerowyEntry
        fields = ("autor", "rok", "dyscyplina_naukowa")
