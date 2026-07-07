from django.contrib import admin

from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow


@admin.register(Obslugujacy_Zgloszenia_Wydzialow)
class Obslugujacy_Zgloszenia_WydzialowAdmin(admin.ModelAdmin):
    list_select_related = ["user", "wydzial"]
    list_display = ["user", "wydzial"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "wydzial":
            from bpp.models import Jednostka

            kwargs["queryset"] = Jednostka.objects.filter(parent__isnull=True)
            kwargs["label"] = "Jednostka (i podrzędne)"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
