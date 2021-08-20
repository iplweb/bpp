from django.contrib.admin import SimpleListFilter

from bpp.admin.filters import SimpleNotNullFilter
from bpp.models import Autor, Wydawca, Zrodlo
from bpp.models.cache import Rekord
from bpp.models.jednostka import Jednostka


class OdpowiednikWBPPFilter(SimpleListFilter):
    db_field_name = None
    klass = Rekord
    fld = "pbn_uid_id"
    title = "Odpowiednik w BPP"
    db_field_name = "pk"
    parameter_name = "odpowiednik"

    def lookups(self, request, model_admin):
        return [("brak", "brak odpowiednika"), ("jest", "ma odpowiednik")]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        query = {
            field
            + "__in": self.klass.objects.exclude(**{self.fld: None})
            .exclude(**{self.fld: ""})
            .values_list(self.fld, flat=True)
            .distinct()
        }

        if v == "brak":
            return queryset.exclude(**query)
        elif v == "jest":
            return queryset.filter(**query)

        return queryset


class OdpowiednikPublikacjiInstytucjiPublikacjaWBPPFilter(OdpowiednikWBPPFilter):
    db_field_name = "publicationId_id"
    title = "Odpowiednik publikacji w BPP"


OdpowiednikOswiadczeniaInstytucjiPublikacjaWBPPFilter = (
    OdpowiednikPublikacjiInstytucjiPublikacjaWBPPFilter
)


class OdpowiednikPublikacjiInstytucjiAutorWBPPFilter(OdpowiednikWBPPFilter):
    db_field_name = "insPersonId_id"
    title = "Odpowiednik autora w BPP"
    parameter_name = "odpowiednik_autora"
    klass = Autor


class OdpowiednikOswiadczeniaInstytucjiAutorWBPPFilter(
    OdpowiednikPublikacjiInstytucjiAutorWBPPFilter
):
    db_field_name = "personId_id"
    klass = Autor


class OdpowiednikJednostkiWBPPFilter(OdpowiednikWBPPFilter):
    klass = Jednostka


class OdpowiednikWydawcyWBPPFilter(OdpowiednikWBPPFilter):
    klass = Wydawca


class OdpowiednikAutoraWBPPFilter(OdpowiednikWBPPFilter):
    klass = Autor


class OdpowiednikZrodlaWBPPFilter(OdpowiednikWBPPFilter):
    klass = Zrodlo


class MaMNISWIDFilter(SimpleNotNullFilter):
    title = "Rekord ma MNISW ID"
    parameter_name = "mniswId"
