"""W tym pakiecie znajdują się procedury generujące raporty, które są dostępne
"od ręki" -- generowane za pomocą WWW"""

from urllib.parse import urlencode

from django.http.response import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.edit import FormView

from .ranking_autorow import *  # noqa

from bpp.models import Rekord
from bpp.views.raporty.forms import RankingAutorowForm


class RankingAutorowFormularz(FormView):
    form_class = RankingAutorowForm
    nazwa_raportu = "Ranking autorow"

    template_name = "raporty/strona_raportow/podstrona.html"
    success_url = "."

    def get_context_data(self, **kwargs):
        data = FormView.get_context_data(self, **kwargs)
        data["nazwa_raportu"] = self.nazwa_raportu
        return data

    def get_lata(self):
        return (
            Rekord.objects.all()
            .values_list("rok", flat=True)
            .order_by("rok")
            .distinct()
        )

    def get_form_kwargs(self, **kw):
        data = FormView.get_form_kwargs(self, **kw)
        data["lata"] = self.get_lata()
        return data

    def get_raport_arguments(self, form):
        return form.cleaned_data

    def form_valid(self, form):
        url = reverse(
            "bpp:ranking-autorow",
            args=(
                form.cleaned_data["od_roku"],
                form.cleaned_data["do_roku"],
            ),
        )

        params = {}

        w = form.cleaned_data["wydzialy"]
        if w:
            params["wydzialy[]"] = [x.pk for x in w]

        e = form.cleaned_data["_export"]
        if e:
            params["_export"] = e

        params["rozbij_na_jednostki"] = form.cleaned_data["rozbij_na_jednostki"]
        params["tylko_afiliowane"] = form.cleaned_data["tylko_afiliowane"]
        params["bez_kol_naukowych"] = form.cleaned_data["bez_kol_naukowych"]
        params["bez_nieaktualnych"] = form.cleaned_data["bez_nieaktualnych"]

        return HttpResponseRedirect(url + "?" + urlencode(params))
