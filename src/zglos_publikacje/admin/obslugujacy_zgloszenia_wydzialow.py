from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow

from django.contrib import admin


@admin.register(Obslugujacy_Zgloszenia_Wydzialow)
class Obslugujacy_Zgloszenia_WydzialowAdmin(admin.ModelAdmin):
    list_select_related = ["user", "wydzial"]
    list_display = ["user", "wydzial"]
