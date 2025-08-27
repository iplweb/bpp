from pbn_api.admin import BasePBNAPIAdmin
from pbn_api.models import OsobaZInstytucji

from django.contrib import admin


@admin.register(OsobaZInstytucji)
class OsobaZInstytucjiAdmin(BasePBNAPIAdmin):
    show_full_result_count = False
    list_display = [
        "lastName",
        "firstName",
        "institutionName",
        "polonUuid",
        "title",
        "_from",
        "_to",
        "phdStudent",
    ]

    search_fields = [
        "lastName",
        "firstName",
        "institutionName",
        "title",
        "_from",
        "_to",
    ]

    readonly_fields = list_display
    list_filter = [
        "phdStudent",
        "institutionName",
        "_from",
        "_to",
    ]
