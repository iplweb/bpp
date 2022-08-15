# Register your models here.
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor

from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from bpp.admin.helpers import MODEL_Z_OPLATA_ZA_PUBLIKACJE
from bpp.models import Wydzial


class Zgloszenie_Publikacji_AutorInline(admin.StackedInline):
    model = Zgloszenie_Publikacji_Autor
    # form = Zgloszenie_Publikacji_AutorInlineForm
    # readonly_fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    extra = 0


class WydzialJednostkiPierwszegoAutora(SimpleListFilter):
    title = "wydział 1go autora"
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
            return queryset.filter(**{field: v})

        return queryset


@admin.register(Zgloszenie_Publikacji)
class Zgloszenie_PublikacjiAdmin(admin.ModelAdmin):
    list_display = ["tytul_oryginalny", "utworzono", "email", "status"]
    list_filter = ["status", "email", WydzialJednostkiPierwszegoAutora]

    fields = (
        (
            "tytul_oryginalny",
            "rok",
        )
        + MODEL_Z_OPLATA_ZA_PUBLIKACJE
        + ("email", "status", "strona_www", "plik")
    )

    inlines = [
        Zgloszenie_Publikacji_AutorInline,
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
