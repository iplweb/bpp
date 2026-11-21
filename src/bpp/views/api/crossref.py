"""Funkcje API pomagające stronom synchronizacji danych z CrossRef API"""

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
from bpp.wersjonowanie import zmiana_rekordu


class UstawParametrBaseView(JSONResponseMixin, GroupRequiredMixin, BaseFormView):
    group_required = GR_WPROWADZANIE_DANYCH

    def form_invalid(self, form):
        return self.render_json_response({"status": "error", "errors": form.errors})

    #: Opis zmiany w historii rekordu (admin „Historia").
    opis_zmiany = None

    def form_valid(self, form):
        obj = self.zmieniany_obiekt(form.cleaned_data)
        with zmiana_rekordu(
            self.request.user,
            obj,
            f"{self.opis_zmiany} (porównanie z CrossRef).",
        ) as zmiana:
            # ``modify_object`` zwraca False, gdy nic nie zmienił.
            zmiana.pomin = self.modify_object(form.cleaned_data) is False
        return self.render_json_response({"status": "ok"})

    def zmieniany_obiekt(self, data):
        return data["rekord"].original

    def modify_object(self, data):
        raise NotImplementedError


class UstawiORCIDAutoraView(UstawParametrBaseView):
    form_class = UstawORCIDAutoraForm
    opis_zmiany = "Ustawiono ORCID"

    def zmieniany_obiekt(self, data):
        return data["autor"]

    def modify_object(self, data):
        autor = data["autor"]
        autor.orcid = data["orcid"]
        autor.save()


class UstawStronyView(UstawParametrBaseView):
    form_class = UstawStronyRekorduForm
    opis_zmiany = "Ustawiono strony"

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.strony = data["strony"]
        ro.save()


class UstawTomView(UstawParametrBaseView):
    form_class = UstawTomRekorduForm
    opis_zmiany = "Ustawiono tom"

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.tom = data["tom"]
        ro.save()


class UstawNrZeszytuView(UstawParametrBaseView):
    form_class = UstawNrZeszytuRekorduForm
    opis_zmiany = "Ustawiono numer zeszytu"

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        ro.nr_zeszytu = data["nr_zeszytu"]
        ro.save()


class UstawStreszczenieView(UstawParametrBaseView):
    form_class = UstawStreszczenieRekorduForm
    opis_zmiany = "Dodano streszczenie"

    def modify_object(self, data):
        rekord = data["rekord"]

        ro = rekord.original
        if ro.streszczenia.filter(streszczenie=data["streszczenie"]).exists():
            return False
        ro.streszczenia.create(streszczenie=data["streszczenie"])
