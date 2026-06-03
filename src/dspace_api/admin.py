from django.contrib import admin

from dspace_api.models import Mapowanie_DSpace


@admin.register(Mapowanie_DSpace)
class Mapowanie_DSpaceAdmin(admin.ModelAdmin):
    list_display = ["uczelnia", "charakter_formalny", "collection_uuid", "opis"]
    list_filter = ["uczelnia"]
    autocomplete_fields = ["charakter_formalny"]
    search_fields = ["opis"]
