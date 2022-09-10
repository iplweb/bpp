# Register your models here.
from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

from django.contrib.admin import SimpleListFilter

from bpp.models import Wydzial


class WydzialJednostkiPierwszegoAutora(SimpleListFilter):
    title = "wydział 1-go autora"
    parameter_name = "wydz1a"
    db_field_name = "zgloszenie_publikacji_autor__jednostka__wydzial"

    def lookups(self, request, model_admin):
        return [
            (x.pk, x.nazwa)
            for x in Wydzial.objects.filter(
                pk__in=Zgloszenie_Publikacji_Autor.objects.filter(kolejnosc=0)
                .values_list("jednostka__wydzial__pk")
                .distinct()
            )
        ]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v:
            return queryset.filter(
                **{field: v, "zgloszenie_publikacji_autor__kolejnosc": 0}
            )

        return queryset
