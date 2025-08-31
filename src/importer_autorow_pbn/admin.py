from .models import DoNotRemind

from django.contrib import admin


@admin.register(DoNotRemind)
class DoNotRemindAdmin(admin.ModelAdmin):
    list_display = ["scientist", "ignored_at", "ignored_by", "reason"]
    list_filter = ["ignored_at", "ignored_by"]
    search_fields = [
        "scientist__lastName",
        "scientist__name",
        "scientist__orcid",
        "reason",
    ]
    readonly_fields = ["ignored_at"]
    raw_id_fields = ["scientist"]

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.ignored_by = request.user
        super().save_model(request, obj, form, change)
