import urllib

import django_tables2 as tables
from django.template.defaultfilters import safe
from django.urls import reverse
from django_tables2 import Column

from raport_slotow import const
from raport_slotow.columns import DecimalColumn, SummingColumn
from raport_slotow.models import (
    RaportEwaluacjaUpowaznieniaView,
    RaportUczelniaEwaluacjaView,
    RaportZerowyEntry,
)
from raport_slotow.models.uczelnia import RaportSlotowUczelniaWiersz

from bpp.models import CHARAKTER_SLOTY
from bpp.models.cache import (
    Cache_Punktacja_Autora_Query,
    Cache_Punktacja_Autora_Query_View,
)


class RaportCommonMixin:
    def render_tytul_oryginalny(self, value):
        url = reverse("bpp:browse_rekord", args=(value.pk[0], value.pk[1]))
        return safe(f"<a href={url}>{value}</a>")

    def value_tytul_oryginalny(self, value):
        return value.tytul_oryginalny

    def render_zrodlo_informacje(self, value):
        if hasattr(value, "zrodlo_id") and value.zrodlo_id is not None:
            return f"{value.zrodlo} {value.szczegoly}"
        return f"{value.informacje} {value.szczegoly}"

    def render_autorzy_z_dyscypliny(self, value):
        if value:
            return ", ".join(value)

    def render_liczba_wszystkich_autorow(self, value):
        if value:
            return len(value)


class RaportSlotowAutorTable(RaportCommonMixin, tables.Table):
    class Meta:
        attrs = {"class": "small-table"}
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query_View
        fields = (
            "tytul_oryginalny",
            "autorzy",
            "autorzy_z_dyscypliny",
            "liczba_autorow_z_dyscypliny",
            "liczba_wszystkich_autorow",
            "rok",
            "zrodlo_informacje",
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
    zrodlo_informacje = Column(
        "Źródło / informacje", "rekord", empty_values=(), orderable=False
    )
    pkdaut = SummingColumn("Punkty dla autora", "pkdaut")
    slot = SummingColumn("Slot")
    autorzy_z_dyscypliny = Column(
        "Autorzy z dyscypliny",
        "zapisani_autorzy_z_dyscypliny",
        orderable=False,
    )
    liczba_autorow_z_dyscypliny = Column(
        "Liczba autorów z dyscypliny",
        "zapisani_autorzy_z_dyscypliny",
        orderable=False,
    )
    liczba_wszystkich_autorow = Column(
        "Liczba wszystkich autorów",
        "rekord.opis_bibliograficzny_autorzy_cache",
        orderable=False,
    )

    def render_liczba_autorow_z_dyscypliny(self, value):
        if value:
            return len(value)


class RaportSlotowUczelniaBezJednostekIWydzialowTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = RaportSlotowUczelniaWiersz
        fields = (
            "autor",
            "pbn_id",
            "orcid",
            "dyscyplina",
            "pkd_aut_sum",
            "slot",
            "avg",
        )

    pkd_aut_sum = DecimalColumn("Suma punktów dla autora")
    slot = DecimalColumn("Slot")
    avg = Column("Średnio punktów dla autora na slot")
    dyscyplina = Column()
    pbn_id = Column("PBN ID", "autor.pbn_id")
    orcid = Column("ORCID", "autor.orcid")

    def __init__(self, od_roku, do_roku, slot, *args, **kw):
        self.od_roku = od_roku
        self.do_roku = do_roku
        self.slot = slot
        super().__init__(*args, **kw)

    def render_avg(self, value):
        return round(value, 4)

    def render_autor(self, value):
        url = (
            reverse("raport_slotow:index")
            + "?"
            + urllib.parse.urlencode(
                {
                    "obiekt": value.pk,
                    "od_roku": self.od_roku,
                    "do_roku": self.do_roku,
                    "dzialanie": const.DZIALANIE_SLOT,
                    "slot": self.slot,
                }
            )
        )
        return safe(f"<a href={url}>{value}</a>")

    def value_autor(self, value):
        return value


class RaportSlotowUczelniaTable(RaportSlotowUczelniaBezJednostekIWydzialowTable):
    class Meta:
        empty_text = "Brak danych"
        model = Cache_Punktacja_Autora_Query
        fields = (
            "autor",
            "pbn_id",
            "orcid",
            "jednostka",
            "wydzial",
            "dyscyplina",
            "pkd_aut_sum",
            "slot",
            "avg",
        )

    wydzial = Column("Wydział", accessor="jednostka.wydzial.nazwa")


class RaportSlotowZerowyTable(tables.Table):
    class Meta:
        empty_text = "Brak danych"
        model = RaportZerowyEntry
        fields = (
            "autor",
            "autor__aktualna_jednostka",
            "autor__pbn_id",
            "autor__orcid",
            "lata",
            "dyscyplina_naukowa",
        )


class RaportSlotowEwaluacjaTable(RaportCommonMixin, tables.Table):
    class Meta:
        attrs = {"class": "very-small-table"}
        empty_text = "Brak danych"
        model = RaportUczelniaEwaluacjaView
        fields = (
            "id",
            "tytul_oryginalny",
            "autorzy",
            "rok",
            "zrodlo_lub_wydawnictwo_nadrzedne",
            "informacje",
            "rodzaj_publikacji",
            "liczba_autorow_z_dyscypliny",
            "liczba_wszystkich_autorow",
            "punkty_pk",
            "autor",
            "aktualna_jednostka",
            "pbn_id",
            "orcid",
            "dyscyplina",
            "procent_dyscypliny",
            "subdyscyplina",
            "procent_subdyscypliny",
            "dyscyplina_rekordu",
            "upowaznienie_pbn",
            "profil_orcid",
            "pkdaut",
            "slot",
        )

    id = Column("ID publikacji", "rekord.id")
    tytul_oryginalny = Column("Tytuł oryginalny", "rekord")
    autorzy = Column(
        "Autorzy", "rekord.opis_bibliograficzny_zapisani_autorzy_cache", orderable=False
    )
    aktualna_jednostka = Column(
        "Aktualna jednostka", "autorzy.autor.aktualna_jednostka.nazwa"
    )
    rok = Column("Rok", "rekord.rok", orderable=True)
    zrodlo_informacje = None
    # Column(
    #    "Źródło / informacje", "rekord", empty_values=(), orderable=False
    # )
    zrodlo_lub_wydawnictwo_nadrzedne = Column(
        "Zródło lub wydawnictwo nadrzędne", "rekord", orderable=False
    )
    informacje = Column("Informacje", "rekord")

    upowaznienie_pbn = Column("Upoważnienie PBN", "autorzy")

    profil_orcid = Column("Profil ORCID", "autorzy")

    def render_upowaznienie_pbn(self, value):
        return value.upowaznienie_pbn

    def render_profil_orcid(self, value):
        return value.profil_orcid

    def render_zrodlo_lub_wydawnictwo_nadrzedne(self, value):
        if (
            hasattr(value, "wydawnictwo_nadrzedne_id")
            and value.wydawnictwo_nadrzedne_id is not None
        ):
            return value.wydawnictwo_nadrzedne.tytul_oryginalny
        if hasattr(value, "zrodlo_id") and value.zrodlo_id is not None:
            return value.zrodlo.nazwa
        return "123"

    def render_informacje(self, value):
        if (
            hasattr(value, "wydawnictwo_nadrzedne_id")
            and value.wydawnictwo_nadrzedne_id is not None
        ):
            return value.szczegoly
        return value.informacje

    rodzaj_publikacji = Column("Rodzaj", "rekord")
    liczba_autorow_z_dyscypliny = Column(
        "Liczba autorów z dyscypliny",
        "autorzy_z_dyscypliny",
        orderable=False,
    )
    liczba_wszystkich_autorow = Column(
        "Liczba wszystkich autorów",
        "rekord.opis_bibliograficzny_autorzy_cache",
        orderable=False,
    )
    punkty_pk = Column("PK", "rekord.punkty_kbn")
    autor = Column("Autor ewaluowany", "autorzy.autor")
    pbn_id = Column("PBN ID", "autorzy.autor.pbn_id")
    orcid = Column("ORCID", "autorzy.autor.orcid")
    dyscyplina = Column(
        "Dyscyplina 1", "autor_dyscyplina.dyscyplina_naukowa", orderable=False
    )
    procent_dyscypliny = Column(
        "% dyscypliny 1", "autor_dyscyplina.procent_dyscypliny", orderable=False
    )
    subdyscyplina = Column(
        "Dyscyplina 2", "autor_dyscyplina.subdyscyplina_naukowa", orderable=False
    )
    procent_subdyscypliny = Column(
        "% dyscypliny 2",
        "autor_dyscyplina.procent_subdyscypliny",
        orderable=False,
    )
    dyscyplina_rekordu = Column("dyscyplina rekordu", "autorzy.dyscyplina_naukowa")
    pkdaut = SummingColumn("Punkty dla autora", "pkdaut")
    slot = SummingColumn("Slot")

    def render_liczba_autorow_z_dyscypliny(self, value):
        if value:
            return len(value)

    def render_rodzaj_publikacji(self, value):
        if value.charakter_formalny.charakter_sloty:
            return CHARAKTER_SLOTY[value.charakter_formalny.charakter_sloty]
        if hasattr(value, "zrodlo_id") and value.zrodlo_id is not None:
            return "Artykuł"

    def render_autorzy(self, value):
        if value:
            if len(value) > 100:
                return value[:100] + "(...)"
            return value

    def value_autorzy(self, value):
        return value


class RaportEwaluacjaUpowaznieniaTable(RaportSlotowEwaluacjaTable):
    class Meta:
        attrs = {"class": "very-small-table"}
        model = RaportEwaluacjaUpowaznieniaView
        empty_text = "Brak danych"
        fields = (
            "id",
            "tytul_oryginalny",
            "autorzy",
            "rok",
            "zrodlo_lub_wydawnictwo_nadrzedne",
            "informacje",
            "rodzaj_publikacji",
            "liczba_wszystkich_autorow",
            "punkty_pk",
            "autor",
            "pbn_id",
            "orcid",
            "aktualna_jednostka",
            "dyscyplina",
            "procent_dyscypliny",
            "subdyscyplina",
            "procent_subdyscypliny",
            "dyscyplina_rekordu",
            "upowaznienie_pbn",
            "profil_orcid",
        )

    pkdaut = None
    slot = None

    aktualna_jednostka = Column(
        "Aktualna jednostka", "autorzy.autor.aktualna_jednostka"
    )
