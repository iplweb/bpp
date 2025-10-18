from django.contrib import admin

from pbn_api.admin.mixins import ReadOnlyListChangeFormAdminMixin
from pbn_api.models import OsobaZInstytucji


@admin.register(OsobaZInstytucji)
class OsobaZInstytucjiAdmin(ReadOnlyListChangeFormAdminMixin, admin.ModelAdmin):
    show_full_result_count = False
    autocomplete_fields = ["institutionId", "personId"]
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
