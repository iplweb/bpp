# Register your models here.
from zglos_publikacje.models import Zgloszenie_Publikacji

from django.contrib import admin


@admin.register(Zgloszenie_Publikacji)
class Zgloszenie_PublikacjiAdmin(admin.ModelAdmin):
    list_display = ["tytul_oryginalny", "utworzono", "email", "status"]
    list_filter = ["status", "email"]

    def has_add_permission(self, request):
        return False
