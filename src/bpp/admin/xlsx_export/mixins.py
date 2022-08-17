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
