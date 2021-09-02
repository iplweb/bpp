from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.models import Conference

from django.contrib import admin


@admin.register(Conference)
class ConferenceAdmin(BaseMongoDBAdmin):
    list_display = [
        "fullName",
        "startDate",
        "endDate",
        "city",
        "country",
        "website",
        "mongoId",
    ]
