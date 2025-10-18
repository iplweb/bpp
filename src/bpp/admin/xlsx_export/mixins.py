from django.conf import settings
from django.contrib import messages
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from import_export.admin import ExportMixin
from import_export.forms import ExportForm
from import_export.signals import post_export

from .formats import PrettyXLSX
from .resources import BibTeXFormat


class PrettyXLSXDefaultExportForm(ExportForm):
    """Export form with PrettyXLSX as default selection."""

    def __init__(self, formats, *args, **kwargs):
        super().__init__(formats, *args, **kwargs)
        # Set PrettyXLSX as default if it's available
        if len(formats) > 0:
            # Find the index of PrettyXLSX format
            for i, format_class in enumerate(formats):
                if (
                    hasattr(format_class, "__name__")
                    and format_class.__name__ == "PrettyXLSX"
                ):
                    self.fields["file_format"].initial = str(i)
                    break
            else:
                # If PrettyXLSX not found, use first format as fallback
                self.fields["file_format"].initial = "0"


class EksportDanychMixin(ExportMixin):
    """Klasa do eksportu danych, bazująca na django-import-export,

    włącza pozwolenie na eksport, gdy na liście admina changelist jest wyświetlane
     poniżej max_allowed_items. Gdy elementów jest więcej, eksport jest niedozwolony,

    eksportuje wyłącznie do XLSX w wersji upiększonej -- automatyczne szerokości wierszy,
    format tableki itp"""

    max_allowed_export_items = None

    def has_export_permission(self, request):
        try:
            cl = self.get_changelist_instance(request)
        except IncorrectLookupParameters:
            return

        max_allowed_export_items = self.max_allowed_export_items
        if max_allowed_export_items is None:
            max_allowed_export_items = getattr(
                settings, "BPP_MAX_ALLOWED_EXPORT_ITEMS", 100
            )

        if cl.result_count < max_allowed_export_items:
            return True

    def export_action(self, request, *args, **kwargs):
        """Eksportuj zawsze do XLSX z upiększaniem -- autorozmiar wierszy + format jako tabela."""
        if not self.has_export_permission(request):
            raise PermissionDenied

        file_format = PrettyXLSX()

        queryset = self.get_export_queryset(request)
        export_data = self.get_export_data(file_format, queryset, request=request)
        content_type = file_format.get_content_type()

        response = HttpResponse(export_data, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="{self.get_export_filename(request, queryset, file_format)}"'
        )

        post_export.send(sender=None, model=self.model)
        return response


class EksportDanychZFormatowanieMixin(ExportMixin):
    """Klasa do eksportu danych z obsługą wyboru formatu (XLSX, BibTeX).

    Rozszerza standardową funkcjonalność eksportu o możliwość wyboru między
    formatami XLSX (domyślny z upiększaniem) i BibTeX.
    """

    max_allowed_export_items = None
    bibtex_resource_class = None  # To be set in subclasses
    export_form_class = PrettyXLSXDefaultExportForm

    def get_export_formats(self):
        """
        Return available export formats.
        """
        formats = (PrettyXLSX, BibTeXFormat)
        return [f for f in formats if f().can_export()]

    def get_resource_class_for_format(self, file_format):
        """
        Get appropriate resource class based on export format.
        """
        if isinstance(file_format, BibTeXFormat) and self.bibtex_resource_class:
            return self.bibtex_resource_class
        return self.resource_class

    def get_export_data(self, file_format, queryset, *args, **kwargs):
        """
        Override to use format-specific resource classes.
        """
        if isinstance(file_format, BibTeXFormat) and self.bibtex_resource_class:
            # Use BibTeX-specific resource
            resource = self.bibtex_resource_class()
            return resource.export(queryset, *args, **kwargs)
        else:
            # Use default resource
            return super().get_export_data(file_format, queryset, *args, **kwargs)

    def has_export_permission(self, request):
        try:
            cl = self.get_changelist_instance(request)
        except IncorrectLookupParameters:
            return

        max_allowed_export_items = self.max_allowed_export_items
        if max_allowed_export_items is None:
            max_allowed_export_items = getattr(
                settings, "BPP_MAX_ALLOWED_EXPORT_ITEMS", 100
            )

        if cl.result_count < max_allowed_export_items:
            return True

    def get_export_queryset(self, request):
        """
        Jedyna roznica vs ExportMixin to ta linia:

            "list_select_related": self.get_list_select_related(request),

        Usunąć tą funkcję po poprawce:

            https://github.com/django-import-export/django-import-export/issues/1493

        """
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        if self.get_actions(request):
            list_display = ["action_checkbox"] + list(list_display)

        ChangeList = self.get_changelist(request)
        changelist_kwargs = {
            "request": request,
            "model": self.model,
            "list_display": list_display,
            "list_display_links": list_display_links,
            "list_filter": list_filter,
            "date_hierarchy": self.date_hierarchy,
            "search_fields": search_fields,
            "list_select_related": self.get_list_select_related(request),
            "list_per_page": self.list_per_page,
            "list_max_show_all": self.list_max_show_all,
            "list_editable": self.list_editable,
            "model_admin": self,
            "search_help_text": "Wyszukaj...",
        }
        import django

        if django.VERSION >= (2, 1):
            changelist_kwargs["sortable_by"] = self.sortable_by
        cl = ChangeList(**changelist_kwargs)

        return cl.get_queryset(request)


class ExportActionsMixin:
    """Mixin that provides BibTeX and XLSX export actions for selected items in admin."""

    def export_selected_bibtex(self, request, queryset):
        """Export selected items as BibTeX."""
        max_allowed_export_items = getattr(self, "max_allowed_export_items", None)
        if max_allowed_export_items is None:
            max_allowed_export_items = getattr(
                settings, "BPP_MAX_ALLOWED_EXPORT_ITEMS", 100
            )

        queryset = queryset[:max_allowed_export_items]

        if hasattr(self, "bibtex_resource_class") and self.bibtex_resource_class:
            try:
                resource = self.bibtex_resource_class()
                dataset = resource.export(queryset)
                response = HttpResponse(
                    str(dataset), content_type="text/plain; charset=utf-8"
                )
                response["Content-Disposition"] = 'attachment; filename="export.bib"'
                return response
            except Exception as e:
                self.message_user(
                    request, f"Error exporting to BibTeX: {e}", level=messages.ERROR
                )
                return None
        self.message_user(
            request,
            "BibTeX export is not available for this model.",
            level=messages.WARNING,
        )

    def export_selected_xlsx(self, request, queryset):
        """Export selected items as XLSX."""
        max_allowed_export_items = getattr(self, "max_allowed_export_items", None)
        if max_allowed_export_items is None:
            max_allowed_export_items = getattr(
                settings, "BPP_MAX_ALLOWED_EXPORT_ITEMS", 100
            )

        queryset = queryset[:max_allowed_export_items]

        file_format = PrettyXLSX()
        if hasattr(self, "resource_class") and self.resource_class:
            try:
                resource = self.resource_class()
                dataset = resource.export(queryset)
                export_data = file_format.export_data(dataset)
                response = HttpResponse(
                    export_data, content_type=file_format.get_content_type()
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="export.{file_format.get_extension()}"'
                )
                return response
            except Exception as e:
                self.message_user(
                    request, f"Error exporting to XLSX: {e}", level=messages.ERROR
                )
                return None
        self.message_user(
            request,
            "XLSX export is not available for this model.",
            level=messages.WARNING,
        )

    export_selected_bibtex.short_description = "Eksportuj wybrane jako BibTeX"
    export_selected_xlsx.short_description = "Eksportuj wybrane jako XLSX"

    def get_actions(self, request):
        """Override to include export actions."""
        actions = super().get_actions(request)

        # Create wrapper functions that have the correct signature
        def export_bibtex_action(modeladmin, request, queryset):
            return modeladmin.export_selected_bibtex(request, queryset)

        def export_xlsx_action(modeladmin, request, queryset):
            return modeladmin.export_selected_xlsx(request, queryset)

        # Set short descriptions
        export_bibtex_action.short_description = "Eksportuj wybrane jako BibTeX"
        export_xlsx_action.short_description = "Eksportuj wybrane jako XLSX"

        actions["export_selected_bibtex"] = (
            export_bibtex_action,
            "export_selected_bibtex",
            export_bibtex_action.short_description,
        )
        actions["export_selected_xlsx"] = (
            export_xlsx_action,
            "export_selected_xlsx",
            export_xlsx_action.short_description,
        )
        return actions
