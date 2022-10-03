from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from import_export.admin import ExportMixin
from import_export.signals import post_export

from .formats import PrettyXLSX

from django.contrib.admin.options import IncorrectLookupParameters


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
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(
            self.get_export_filename(request, queryset, file_format),
        )

        post_export.send(sender=None, model=self.model)
        return response

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
        }
        import django

        if django.VERSION >= (2, 1):
            changelist_kwargs["sortable_by"] = self.sortable_by
        cl = ChangeList(**changelist_kwargs)

        return cl.get_queryset(request)
