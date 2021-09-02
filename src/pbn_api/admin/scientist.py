from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikAutoraWBPPFilter
from pbn_api.models import Scientist

from django.contrib import admin

from bpp.admin.filters import OrcidObecnyFilter


@admin.register(Scientist)
class ScientistAdmin(BaseMongoDBAdmin):
    show_full_result_count = False
    list_display = [
        "lastName",
        "name",
        "qualifications",
        "polonUid",
        "orcid",
        "currentEmploymentsInstitutionDisplayName",
        "mongoId",
        "from_institution_api",
        "rekord_w_bpp",
    ]

    search_fields = [
        "mongoId",
        "lastName",
        "name",
        "orcid",
    ]

    fields = BaseMongoDBAdmin.fields + [
        "from_institution_api",
    ]
    readonly_fields = BaseMongoDBAdmin.readonly_fields + ["from_institution_api"]
    list_filter = [
        OdpowiednikAutoraWBPPFilter,
        OrcidObecnyFilter,
        "from_institution_api",
        "qualifications",
    ] + BaseMongoDBAdmin.list_filter
