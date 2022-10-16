"""Funkcje API pomagające stronom synchronizacji danych z CrossRef API
"""

from braces.views import GroupRequiredMixin, JSONResponseMixin
from django.views.generic.edit import BaseFormView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.views.api.forms import (
    UstawNrZeszytuRekorduForm,
    UstawORCIDAutoraForm,
    UstawStreszczenieRekorduForm,
    UstawStronyRekorduForm,
    UstawTomRekorduForm,
)


class UstawParametrBaseView(JSONResponseMixin, GroupRequiredMixin, BaseFormView):
    group_required = GR_WPROWADZANIE_DANYCH

    def form_invalid(self, form):
        return self.render_json_response({"status": "error", "errors": form.errors})

    def form_valid(self, form):
        self.modify_object(form.cleaned_data)
        return self.render_json_response({"status": "ok"})

    def modify_object(self, data):
        raise NotImplementedError


class UstawiORCIDAutoraView(UstawParametrBaseView):
    form_class = UstawORCIDAutoraForm

    def modify_object(self, data):
        autor = data["autor"]
        autor.orcid = data["orcid"]
        autor.save()


class UstawStronyView(UstawParametrBaseView):
    form_class = UstawStronyRekorduForm

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.strony = data["strony"]
        ro.save()


class UstawTomView(UstawParametrBaseView):
    form_class = UstawTomRekorduForm

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.tom = data["tom"]
        ro.save()


class UstawNrZeszytuView(UstawParametrBaseView):
    form_class = UstawNrZeszytuRekorduForm

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.nr_zeszytu = data["nr_zeszytu"]
        ro.save()


class UstawStreszczenieView(UstawParametrBaseView):
    form_class = UstawStreszczenieRekorduForm

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        if not ro.streszczenia.filter(streszczenie=data["streszczenie"]).exists():
            ro.streszczenia.create(streszczenie=data["streszczenie"])
