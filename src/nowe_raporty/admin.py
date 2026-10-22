from django.contrib import admin
from flexible_reports.admin.report import ReportAdmin
from flexible_reports.models import Report

from .models import DefinicjaRaportu, utworz_definicje_dla


class BppReportAdmin(ReportAdmin):
    """``ReportAdmin`` z flexible-reports, który zakłada definicję nowego raportu.

    Bez definicji raport nie trafia do menu "raporty" na stronie. Hak siedzi
    w ``log_addition``, bo przez nią przechodzą oba sposoby dodania raportu
    w adminie: formularz (po zapisaniu inline'ów) i "Klonuj". Celowo NIE jest
    to sygnał ``post_save``: seeding i kod tworzący ``Report`` programowo sam
    zakłada definicje z właściwymi uprawnieniami.
    """

    def log_addition(self, request, obj, message):
        utworz_definicje_dla(obj)
        return super().log_addition(request, obj, message)


admin.site.unregister(Report)
admin.site.register(Report, BppReportAdmin)


@admin.register(DefinicjaRaportu)
class DefinicjaRaportuAdmin(admin.ModelAdmin):
    list_display = [
        "nazwa",
        "poziom",
        "report",
        "poziom_dostepu",
        "aktywny",
        "kolejnosc",
    ]
    list_editable = ["aktywny", "kolejnosc"]
    list_filter = ["poziom", "poziom_dostepu", "aktywny"]
    search_fields = ["nazwa", "slug"]
    prepopulated_fields = {"slug": ("nazwa",)}
    filter_horizontal = ["wymagane_grupy", "uczelnie"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "nazwa",
                    "slug",
                    "poziom",
                    "report",
                    "kolejnosc",
                    "aktywny",
                ]
            },
        ),
        (
            "Uprawnienia i widoczność",
            {
                "fields": ["poziom_dostepu", "wymagane_grupy", "uczelnie"],
                "description": "Kto widzi raport (poziom dostępu + opcjonalne "
                "grupy) i na stronach których uczelni się pojawia "
                "(puste = wszędzie).",
            },
        ),
    ]
