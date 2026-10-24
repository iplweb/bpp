from django import forms
from django.contrib import admin
from flexible_reports.admin.report import ReportAdmin
from flexible_reports.models import Report

from . import ikony
from .models import DefinicjaRaportu, utworz_definicje_dla


class WyborIkonyWidget(forms.RadioSelect):
    """Siatka ikon Foundation z podglądem — nazwa klasy sama nic nie mówi."""

    template_name = "admin/nowe_raporty/wybor_ikony.html"
    option_template_name = "admin/nowe_raporty/wybor_ikony_opcja.html"

    class Media:
        # Admin nie ładuje fontu ikon (ten jest tylko w ``bare.html`` strony).
        css = {
            "all": [
                "foundation-datepicker/foundation/fonts/foundation-icons.css",
                "nowe_raporty/wybor_ikony.css",
            ]
        }


class DefinicjaRaportuForm(forms.ModelForm):
    ikona = forms.ChoiceField(
        label="Ikona w menu",
        required=False,
        choices=[("", "domyślna dla poziomu")] + ikony.WYBORY,
        widget=WyborIkonyWidget,
        help_text="Brak wyboru = ikona zależna od poziomu raportu.",
    )

    class Meta:
        model = DefinicjaRaportu
        # Admin i tak bierze listę pól z ``fieldsets``; tu tylko pole własne.
        fields = ["ikona"]


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
    form = DefinicjaRaportuForm
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
        ("Ikona w menu", {"fields": ["ikona"]}),
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
