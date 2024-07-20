from django.contrib import admin

from bpp.admin.wydawnictwo_autor_base import Wydawnictwo_Autor_Base
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


@admin.register(Wydawnictwo_Ciagle_Autor)
class Wydawnictwo_Ciagle_Autor_Admin(Wydawnictwo_Autor_Base):
    klasa_autora = Wydawnictwo_Ciagle_Autor
    base_rekord_class = Wydawnictwo_Ciagle
    change_list_template = "admin/bpp/wydawnictwo_ciagle_autor/change_list.html"
    import_export_change_list_template = (
        "admin/bpp/wydawnictwo_ciagle_autor/change_list.html"
    )

    def _changeform_view(self, request, object_id, form_url, extra_context):
        if extra_context is None:
            extra_context = {}
        rekord_pk = self.get_changeform_initial_data(request).get("rekord", None)
        if rekord_pk is not None:
            rok = Wydawnictwo_Ciagle.objects.get(pk=rekord_pk).rok
            extra_context["rok"] = rok
        return super()._changeform_view(request, object_id, form_url, extra_context)
