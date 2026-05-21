from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from snapshot_odpiec.tasks import suma_odpietych_dyscyplin, suma_przypietych_dyscyplin

from .models import SnapshotOdpiec


class ListaSnapshotow(GroupRequiredMixin, ListView):
    group_required = "raporty"
    model = SnapshotOdpiec
    ordering = "-created_on"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            przypiete=suma_przypietych_dyscyplin(),
            odpiete=suma_odpietych_dyscyplin(),
            **kwargs,
        )


class AplikujSnapshot(GroupRequiredMixin, DetailView):
    """GET wyświetla potwierdzenie, POST aplikuje snapshot na bazę."""

    model = SnapshotOdpiec
    group_required = "raporty"
    template_name = "snapshot_odpiec/aplikuj_confirm.html"

    def post(self, *args, **kw):
        self.object: SnapshotOdpiec = self.get_object()
        self.object.apply()
        messages.info(
            self.request, f"Zaaplikowano snapshot odpięć nr {self.object.pk}."
        )
        return HttpResponseRedirect(reverse("snapshot_odpiec:index"))


class NowySnapshot(GroupRequiredMixin, View):
    """GET wyświetla potwierdzenie, POST tworzy nowy snapshot."""

    group_required = "raporty"
    template_name = "snapshot_odpiec/nowy_confirm.html"

    def get(self, request, *args, **kw):
        from django.shortcuts import render

        return render(request, self.template_name)

    def post(self, request, *args, **kw):
        SnapshotOdpiec.objects.create(owner=request.user, comment="utworzony ręcznie")
        messages.info(request, "Utworzono snapshot odpięć")
        return HttpResponseRedirect(reverse("snapshot_odpiec:index"))
