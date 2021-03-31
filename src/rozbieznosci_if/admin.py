# Register your models here.
from rozbieznosci_if.models import IgnorujRozbieznoscIf

from django.contrib import admin


@admin.register(IgnorujRozbieznoscIf)
class IgnorujRozbieznoscIfAdmin(admin.ModelAdmin):
    list_display = ["object", "created_on"]
