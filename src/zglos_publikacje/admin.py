# Register your models here.
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    Zgloszenie_Publikacji_Plik,
)

from django.contrib import admin


class Zgloszenie_Publikacji_AutorInline(admin.StackedInline):
    model = Zgloszenie_Publikacji_Autor
    # form = Zgloszenie_Publikacji_AutorInlineForm
    # readonly_fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    extra = 0


class Zgloszenie_Publikacji_PlikInline(admin.TabularInline):
    model = Zgloszenie_Publikacji_Plik
    extra = 0


@admin.register(Zgloszenie_Publikacji)
class Zgloszenie_PublikacjiAdmin(admin.ModelAdmin):
    list_display = ["tytul_oryginalny", "utworzono", "email", "status"]
    list_filter = ["status", "email"]

    inlines = [Zgloszenie_Publikacji_AutorInline, Zgloszenie_Publikacji_PlikInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
