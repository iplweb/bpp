from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from bpp.models import Autor, Cache_Punktacja_Autora_Query
from bpp.views.mixins import UczelniaSettingRequiredMixin
from raport_slotow.forms import AutorRaportSlotowForm


class WyborOsoby(UczelniaSettingRequiredMixin, FormView):
    template_name = "raport_slotow/index.html"
    form_class = AutorRaportSlotowForm
    uczelnia_attr = "pokazuj_raport_slotow"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Wybór autora'
        return context

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        return HttpResponseRedirect(
            reverse("raport_slotow:raport", kwargs={"autor": form.cleaned_data['obiekt'].slug,
                                                    "od_roku": form.cleaned_data['od_roku'],
                                                    "do_roku": form.cleaned_data['do_roku'],
                                                    "export": form.cleaned_data['_export']})
        )


class RaportSlotow(UczelniaSettingRequiredMixin, ListView):
    template_name = "raport_slotow/raport.html"
    context_object_name = "lista"
    uczelnia_attr = "pokazuj_raport_slotow"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(RaportSlotow, self).get_context_data(**kwargs)
        context['autor'] = self.autor
        context['od_roku'] = self.od_roku
        context['do_roku'] = self.do_roku
        return context

    def get_queryset(self):
        self.autor = get_object_or_404(Autor, slug=self.kwargs.get("autor"))
        try:
            self.od_roku = int(self.kwargs.get("od_roku"))
            self.do_roku = int(self.kwargs.get("do_roku"))
        except (TypeError, ValueError):
            raise Http404

        return Cache_Punktacja_Autora_Query.objects.filter(autor=self.autor,
                                                           rekord__rok__gte=self.od_roku,
                                                           rekord__rok__lte=self.do_roku,
                                                           pkdaut__gt=0).select_related(
            "rekord", "dyscyplina",
        )

    pass
