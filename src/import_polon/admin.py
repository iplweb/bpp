from django.contrib import admin

from .models import ImportPolonOverride


@admin.register(ImportPolonOverride)
class ImportPolonOverrideAdmin(admin.ModelAdmin):
    list_display = ("grupa_stanowisk", "jest_badawczy")
    search_fields = ("grupa_stanowisk",)
    list_filter = ("jest_badawczy",)
