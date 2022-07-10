"""W tym pakiecie znajdują się procedury generujące raporty, które są dostępne
"od ręki" -- generowane za pomocą WWW"""
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DetailView, View
from django.views.generic.base import TemplateView
from django.views.generic.edit import BaseDeleteView, FormView
from sendfile import sendfile

from celeryui.interfaces import IWebTask
from celeryui.models import Report
from .ranking_autorow import *  # noqa
from .raport_jednostek_2012 import *  # noqa

from django.contrib import messages

from bpp.models import Rekord
from bpp.views.raporty.forms import (
    RankingAutorowForm,
    RaportAutorowForm,
    RaportDlaKomisjiCentralnejForm,
    RaportJednostekForm,
)


class PobranieRaportu(View):
    """Domyślnie dajemy wszystkim zalogowanym, którzy znają link,
    możliwość pobrania raportu."""

    def get(self, request, uid, *args, **kwargs):
        try:
            raport = Report.objects.filter(uid=uid).exclude(finished_on=None)[0]
        except IndexError:
            raise Http404

        return sendfile(request, raport.file.path, attachment=True)


class PodgladRaportu(DetailView):
    """Domyślnie dajemy wszystkim zalogowanym, którzy znają link,
    możliwość podejrzenia raportu."""

    template_name = "raporty/podglad_raportu.html"

    def get_object(self, queryset=None):
        try:
            raport = Report.objects.get(uid=self.kwargs["uid"])
        except Report.DoesNotExist:
            raise Http404

        return raport


class KasowanieRaportu(BaseDeleteView):
    slug_field = "uid"
    success_url = "../../.."

    def get_object(self):
        try:
            return Report.objects.get(
                uid=self.kwargs["uid"], ordered_by=self.request.user
            )
        except Report.DoesNotExist:
            raise Http404

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()

        try:
            obj.file.path
        except ValueError:
            pass

        response = BaseDeleteView.delete(self, request, *args, **kwargs)
        messages.add_message(request, messages.INFO, "Raport został usunięty.")
        return response

    def render_to_response(self, *args, **kwargs):
        return self.delete(self.request, *args, **kwargs)


class RaportyMixin:
    def get_raporty(self):
        raporty = Report.objects.filter(ordered_by=self.request.user)
        for raport in raporty:
            raport.adapted = IWebTask(raport)
        return raporty

    def get_lata(self):
        return (
            Rekord.objects.all()
            .values_list("rok", flat=True)
            .order_by("rok")
            .distinct()
        )


class RaportyFormMixin(RaportyMixin):
    template_name = "raporty/strona_raportow/podstrona.html"
    success_url = "."
    nazwa_raportu = "skonfiguruj-mnie"

    def get_context_data(self, **kwargs):
        data = FormView.get_context_data(self, **kwargs)
        data["raporty"] = []
        if not self.request.user.is_anonymous:
            data["raporty"] = self.get_raporty()
        data["nazwa_raportu"] = self.nazwa_raportu
        return data

    def get_form_kwargs(self, **kw):
        data = FormView.get_form_kwargs(self, **kw)
        data["lata"] = self.get_lata()
        return data

    def get_raport_arguments(self, form):
        return form.cleaned_data

    def form_valid(self, form):
        r = Report.objects.create(
            ordered_by=self.request.user,
            function=self.request.POST["report"],
            arguments=self.get_raport_arguments(form),
        )

        if self.request.POST.get("do_not_call_celery") != "1":
            from bpp.tasks import make_report

            make_report.delay(r.uid)

        messages.add_message(
            self.request,
            messages.INFO,
            "Zamówienie raportu zostało złożone. Zostaniesz poinformowany/a "
            "na bieżąco o zakończeniu jego generowania.",
        )

        return FormView.form_valid(self, form)


class RaportCommonView(RaportyFormMixin, FormView):
    def form_valid(self, form):
        rok_min = form.cleaned_data["od_roku"]
        rok_max = form.cleaned_data["do_roku"]
        object = form.cleaned_data[self.object_key].pk
        output = "html"
        if form.cleaned_data["output"]:
            output = "msw"

        if rok_min != rok_max:
            url = (
                reverse(self.url_min_max, args=(object, rok_min, rok_max))
                + "?output=%s" % output
            )
            return HttpResponseRedirect(url)

        url = reverse(self.url_single, args=(object, rok_min)) + "?output=%s" % output
        return HttpResponseRedirect(url)


class RaportJednostek(RaportCommonView):
    form_class = RaportJednostekForm
    nazwa_raportu = "Raport jednostek"
    object_key = "jednostka"
    url_min_max = "bpp:raport-jednostek-rok-min-max"
    url_single = "bpp:raport-jednostek"


class RaportAutorow(RaportCommonView):
    form_class = RaportAutorowForm
    nazwa_raportu = "Raport autorów"
    object_key = "autor"
    url_min_max = "bpp:raport-autorow-rok-min-max"
    url_single = "bpp:raport-autorow"
    #
    # def form_valid(self, form):
    #     rok_min = form.cleaned_data['od_roku']
    #     rok_max = form.cleaned_data['do_roku']
    #     autor = form.cleaned_data['autor'].pk
    #
    #     if rok_min != rok_max:
    #         return HttpResponseRedirect(
    #             reverse(
    #                 "bpp:raport-autorow-rok-min-max",
    #                 args=(autor, rok_min, rok_max)))
    #
    #     return HttpResponseRedirect(
    #         reverse("bpp:raport-autorow", args=(autor, rok_min)))


class RankingAutorowFormularz(RaportyFormMixin, FormView):
    form_class = RankingAutorowForm
    nazwa_raportu = "Ranking autorow"

    def form_valid(self, form):
        url = reverse(
            "bpp:ranking-autorow",
            args=(
                form.cleaned_data["od_roku"],
                form.cleaned_data["do_roku"],
            ),
        )

        w = form.cleaned_data["wydzialy"]
        if w:
            url += "?"
            url += "&".join(["wydzialy[]=%s" % x.pk for x in w])

        e = form.cleaned_data["_export"]
        if e:
            if url.find("?") < 0:
                url += "?"
            else:
                url += "&"
            url += f"_export={ e }"

        r = form.cleaned_data["rozbij_na_jednostki"]
        if url.find("?") < 0:
            url += "?"
        else:
            url += "&"
        url += f"rozbij_na_jednostki={ r }"

        ta = form.cleaned_data["tylko_afiliowane"]
        if url.find("?") < 0:
            url += "?"
        else:
            url += "&"
        url += f"tylko_afiliowane={ ta }"

        return HttpResponseRedirect(url)


class RaportDlaKomisjiCentralnejFormularz(RaportyFormMixin, FormView):
    form_class = RaportDlaKomisjiCentralnejForm
    nazwa_raportu = "Raport dla Komisji Centralnej"

    def get_raport_arguments(self, form):
        form.cleaned_data["autor"] = form.cleaned_data["autor"].pk
        return form.cleaned_data


class RaportSelector(RaportyMixin, TemplateView):
    template_name = "raporty/strona_raportow/index.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(raporty=self.get_raporty(), **kwargs)
