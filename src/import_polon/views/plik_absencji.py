from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView

from import_polon.forms import NowyImportAbsencjiForm
from import_polon.models import ImportPlikuAbsencji
from import_polon.views.plik_polon import (
    BaseImportPlikuPolonMixin,
    ZapiszDoBazyMixin,
    _PkOwnerRestartMixin,
)


class BaseImportPlikuAbsencjiMixin(BaseImportPlikuPolonMixin):
    model = ImportPlikuAbsencji


class PokazImportyAbsencji(BaseImportPlikuAbsencjiMixin, ListView):
    """Lista importów absencji bieżącego użytkownika (owner-scoped).

    Absencje NIE mają pola ``uczelnia`` (import globalny, nie per-uczelnia),
    więc bez zawężenia multi-hosted. Bugfix: dawniej ``index-absencji``
    mapował na ``PokazImporty`` (listę POLON) — teraz ma własny widok +
    szablon ``importplikuabsencji_list.html``.
    """

    max_previous_ops = 10
    template_name = "import_polon/importplikuabsencji_list.html"

    def get_queryset(self):
        qset = self.model.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )
        for elem in qset[self.max_previous_ops :]:
            elem.delete()
        return qset


class UtworzImportPlikuAbsencji(BaseImportPlikuAbsencjiMixin, CreateLiveOperationView):
    form_class = NowyImportAbsencjiForm


class RestartImportAbsencjiView(_PkOwnerRestartMixin):
    model = ImportPlikuAbsencji


class ZapiszDoBazyImportAbsencjiView(BaseImportPlikuAbsencjiMixin, ZapiszDoBazyMixin):
    pass


class ImportAbsencjiResultsView(BaseImportPlikuAbsencjiMixin, ListView):
    paginate_by = 25

    @cached_property
    def parent_object(self):
        return get_object_or_404(
            ImportPlikuAbsencji, pk=self.kwargs["pk"], owner=self.request.user
        )

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def get_context_data(self, **kwargs):
        # object=self.parent_object OBOWIĄZKOWE (szablon woła {% url ... object.pk %}).
        return super().get_context_data(object=self.parent_object, **kwargs)
