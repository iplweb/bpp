from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from bpp.models import Autor, Cache_Punktacja_Autora_Query
from raport_slotow.forms import AutorRaportSlotowForm


class WyborOsoby(FormView, LoginRequiredMixin):
    template_name = "raport_slotow/index.html"
    form_class = AutorRaportSlotowForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Wybór autora'
        return context

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        return HttpResponseRedirect(
            reverse("raport_slotow:raport", kwargs={"autor": form.cleaned_data['obiekt'].slug,
                                                    "rok": form.cleaned_data['rok'],
                                                    "export": form.cleaned_data['_export']})
        )


class RaportSlotow(ListView, LoginRequiredMixin):
    template_name = "raport_slotow/raport.html"
    context_object_name = "lista"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(RaportSlotow, self).get_context_data(**kwargs)
        context['autor'] = self.autor
        context['rok'] = self.rok
        return context

    def get_queryset(self):
        self.autor = get_object_or_404(Autor, slug=self.kwargs.get("autor"))
        try:
            self.rok = int(self.kwargs.get("rok"))
        except (TypeError, ValueError):
            raise Http404

        return Cache_Punktacja_Autora_Query.objects.filter(autor=self.autor, rekord__rok=self.rok,
                                                           pkdaut__gt=0).select_related(
            "rekord", "dyscyplina",
        )

    pass
