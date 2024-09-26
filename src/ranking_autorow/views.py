import itertools
from urllib.parse import urlencode

from django.db.models.aggregates import Sum
from django.http.response import HttpResponseRedirect
from django.template.defaultfilters import safe
from django.urls import reverse
from django.views.generic.edit import FormView
from django_tables2 import Column
from django_tables2.export.views import ExportMixin
from django_tables2.tables import Table
from django_tables2.views import SingleTableView

from .forms import RankingAutorowForm

from django.utils.functional import cached_property

from bpp.models import Autor, Jednostka, OpcjaWyswietlaniaField, Rekord, Sumy, Uczelnia
from bpp.models.struktura import Wydzial


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
        params["bez_nieaktualnych"] = form.cleaned_data["bez_nieaktualnych"]

        return HttpResponseRedirect(url + "?" + urlencode(params))


class RankingAutorowTable(Table):
    class Meta:
        attrs = {"class": "bpp-table"}
        model = Autor
        order_by = ("-impact_factor_sum", "autor__nazwisko")
        fields = (
            "lp",
            "autor",
            "impact_factor_sum",
            "liczba_cytowan_sum",
            "punkty_kbn_sum",
        )

    lp = Column(
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "bpp-lp-column"}},
        exclude_from_export=True,
    )

    autor = Column(order_by=("autor__nazwisko", "autor__imiona"))
    punkty_kbn_sum = Column("Punkty MNiSW/MEiN", "punkty_kbn_sum")
    impact_factor_sum = Column("Impact Factor", "impact_factor_sum")
    liczba_cytowan_sum = Column("Liczba cytowań", "liczba_cytowan_sum")

    def render_lp(self):
        self.lp_counter = getattr(
            self, "lp_counter", itertools.count(self.page.start_index())
        )
        return "%i." % next(self.lp_counter)

    def render_autor(self, record):
        return safe(
            '<a href="%s">%s</a>'
            % (
                reverse("bpp:browse_autor", args=(record.autor.slug,)),
                str(record.autor),
            )
        )

    def value_autor(self, record):
        return str(record.autor)


class RankingAutorowJednostkaWydzialTable(RankingAutorowTable):
    class Meta:
        fields = (
            "lp",
            "autor",
            "jednostka",
            "wydzial",
            "impact_factor_sum",
            "liczba_cytowan_sum",
            "punkty_kbn_sum",
        )
        order_by = ("-impact_factor_sum", "autor__nazwisko")

    jednostka = Column(accessor="jednostka.nazwa")
    wydzial = Column(accessor="jednostka.wydzial.nazwa")


class RankingAutorow(ExportMixin, SingleTableView):
    template_name = "raporty/ranking-autorow.html"

    def get_table_class(self):
        if self.rozbij_na_wydzialy:
            return RankingAutorowJednostkaWydzialTable
        return RankingAutorowTable

    @cached_property
    def rozbij_na_wydzialy(self):
        return self.request.GET.get("rozbij_na_jednostki", "True") == "True"

    @cached_property
    def tylko_afiliowane(self):
        return self.request.GET.get("tylko_afiliowane", "False") == "True"

    @cached_property
    def bez_kol_naukowych(self):
        return getattr(
            Uczelnia.objects.get_for_request(self.request),
            "ranking_autorow_bez_kol_naukowych",
            True,
        )

    @cached_property
    def bez_nieaktualnych(self):
        return self.request.GET.get("bez_nieaktualnych", "True") == "True"

    def get_queryset(self):
        qset = Sumy.objects.all()
        qset = qset.filter(
            rok__gte=self.kwargs["od_roku"], rok__lte=self.kwargs["do_roku"]
        )
        wydzialy = self.get_wydzialy()
        if wydzialy:
            qset = qset.filter(jednostka__wydzial__in=wydzialy)

        if self.tylko_afiliowane:
            qset = qset.filter(jednostka__skupia_pracownikow=True)
            qset = qset.filter(afiliuje=True)

        if self.rozbij_na_wydzialy:
            qset = qset.prefetch_related("jednostka__wydzial").select_related(
                "autor", "jednostka"
            )
            qset = qset.group_by("autor", "jednostka")
        else:
            qset = qset.select_related("autor")
            qset = qset.group_by("autor")

        qset = qset.annotate(
            impact_factor_sum=Sum("impact_factor"),
            liczba_cytowan_sum=Sum("liczba_cytowan"),
            punkty_kbn_sum=Sum("punkty_kbn"),
        )
        qset = qset.exclude(impact_factor_sum=0, liczba_cytowan_sum=0, punkty_kbn_sum=0)

        qset = qset.exclude(autor__pokazuj=False)

        if self.bez_kol_naukowych:
            qset = qset.exclude(
                autor__aktualna_jednostka__rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
            )

        if self.bez_nieaktualnych:
            qset = qset.exclude(autor__aktualna_jednostka=None)

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            ukryte_statusy = uczelnia.ukryte_statusy("rankingi")
            if ukryte_statusy:
                qset = qset.exclude(status_korekty_id__in=ukryte_statusy)

        return qset

    def get_dostepne_wydzialy(self):
        return Wydzial.objects.filter(zezwalaj_na_ranking_autorow=True)

    def get_wydzialy(self):
        base_query = self.get_dostepne_wydzialy()

        wydzialy = self.request.GET.dict().get("wydzialy[]", None)
        if wydzialy:
            wydzialy_pk = []
            try:
                wydzialy_pk = [int(x.strip()) for x in wydzialy[1:-1].split(",")]
            except (TypeError, ValueError):
                pass

            try:
                wydzialy = base_query.filter(pk__in=[pk for pk in wydzialy_pk])
                return wydzialy
            except (TypeError, ValueError):
                pass

        return base_query

    def get_context_data(self, **kwargs):
        context = super(SingleTableView, self).get_context_data(**kwargs)
        context["od_roku"] = self.kwargs["od_roku"]
        context["do_roku"] = self.kwargs["do_roku"]
        jeden_rok = False
        if self.kwargs["od_roku"] == self.kwargs["do_roku"]:
            context["rok"] = self.kwargs["od_roku"]
            jeden_rok = True

        wydzialy = self.get_wydzialy()
        context["wydzialy"] = wydzialy

        if jeden_rok:
            context["table_title"] = "Ranking autorów za rok %s" % context["rok"]
        else:
            context["table_title"] = "Ranking autorów za lata {} - {}".format(
                context["od_roku"],
                context["do_roku"],
            )
        context["tab_subtitle"] = ""
        if len(wydzialy) != len(self.get_dostepne_wydzialy()):
            context["table_subtitle"] = ", ".join([x.nazwa for x in wydzialy])
        return context

    def get_table_kwargs(self):
        uczelnia = Uczelnia.objects.all().first()
        pokazuj = uczelnia.pokazuj_liczbe_cytowan_w_rankingu

        if pokazuj == OpcjaWyswietlaniaField.POKAZUJ_NIGDY or (
            pokazuj == OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
            and self.request.user.is_anonymous
        ):
            return {"exclude": ("liczba_cytowan_sum",)}
        return {}
