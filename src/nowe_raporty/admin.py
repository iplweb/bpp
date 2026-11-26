from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from flexible_reports.admin.datasource import DatasourceAdmin
from flexible_reports.admin.report import ReportAdmin
from flexible_reports.models import Datasource, Report

from bpp.admin.helpers.djangoql import (
    SKRYPT_ESCAPOWANIA_PODPOWIEDZI,
    WIDZET_PODPOWIEDZI,
)

from . import ikony
from .models import DefinicjaRaportu, utworz_definicje_dla
from .powrot import adres_powrotu


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


class BppDatasourceAdmin(DatasourceAdmin):
    """„Źródła danych” z powrotem do raportu, z którego przyszedł redaktor.

    Otwarty raport linkuje tu z parametrem ``powrot`` (FD#448). Po „Zapisz”
    wracamy pod ten adres zamiast na listę źródeł danych — raport generuje się
    od nowa, więc od razu widać efekt zmiany zapytania. Bez parametru formularz
    zachowuje się jak dotąd.
    """

    change_form_template = "admin/nowe_raporty/datasource_change_form.html"

    @property
    def media(self):
        # Edytor zapytania ładuje widżet podpowiedzi DjangoQL; podpowiadane
        # nazwy z bazy mają być tekstem, nie HTML-em. Widżet wymieniony razem
        # ze skryptem, bo Django zachowuje kolejność tylko w obrębie jednej
        # listy, a skrypt musi iść PO widżecie.
        return super().media + forms.Media(
            js=[WIDZET_PODPOWIEDZI, SKRYPT_ESCAPOWANIA_PODPOWIEDZI]
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "powrot_url": adres_powrotu(request),
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        # ``super()`` zawsze: to ono dodaje komunikat „zmieniono pomyślnie”.
        response = super().response_change(request, obj)
        powrot = adres_powrotu(request)
        if powrot is None:
            return response
        # „Zapisz i kontynuuj edycję" zostaje w formularzu (parametr powrotu
        # przenosi samo Django), „…i dodaj nowy" idzie do pustego formularza.
        if any(k in request.POST for k in ("_continue", "_addanother", "_saveasnew")):
            return response
        return HttpResponseRedirect(powrot)


admin.site.unregister(Datasource)
admin.site.register(Datasource, BppDatasourceAdmin)


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
