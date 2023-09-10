from pbn_api.admin.base import BasePBNAPIAdmin
from ..models.discipline import Discipline, DisciplineGroup

from django.contrib import admin


@admin.register(DisciplineGroup)
class DisciplineGroupAdmin(BasePBNAPIAdmin):
    pass


@admin.register(Discipline)
class DisciplineAdmin(BasePBNAPIAdmin):
    search_fields = [
        "name",
        "code",
        "polonCode",
        "scientificFieldName",
        "uuid",
        "parent_group__uuid",
    ]
    list_display = ["name", "code", "polonCode", "scientificFieldName", "parent_group"]
    list_filter = ["parent_group", "scientificFieldName"]
