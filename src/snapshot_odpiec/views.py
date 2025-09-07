from braces.views import GroupRequiredMixin
from django.http import HttpResponseRedirect
from django.views import View
from django.views.generic import DetailView, ListView

from snapshot_odpiec.tasks import suma_odpietych_dyscyplin, suma_przypietych_dyscyplin
from .models import SnapshotOdpiec

from django.contrib import messages


# Create your views here.
class ListaSnapshotow(GroupRequiredMixin, ListView):
    group_required = "raporty"
    model = SnapshotOdpiec
    ordering = "-created_on"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            przypiete=suma_przypietych_dyscyplin(),
            odpiete=suma_odpietych_dyscyplin(),
            **kwargs,
        )


class AplikujSnapshot(GroupRequiredMixin, DetailView):
    model = SnapshotOdpiec
    group_required = "raporty"

    def get(self, *args, **kw):
        self.object: SnapshotOdpiec = self.get_object()
        self.object.apply()
        messages.info(
            self.request, f"Zaaplikowano snapshot odpięć nr {self.object.pk}."
        )
        return HttpResponseRedirect("../../")


class NowySnapshot(GroupRequiredMixin, View):
    group_required = "raporty"

    def get(self, *args, **kw):
        SnapshotOdpiec.objects.create(
            owner=self.request.user, comment="utworzony ręcznie"
        )
        messages.info(self.request, "Utworzono snapshot odpięć")
        return HttpResponseRedirect("..")
