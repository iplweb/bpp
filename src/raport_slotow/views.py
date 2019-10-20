import urllib
from datetime import datetime
from urllib.parse import urlencode

import django_filters
from django.db.models import Window, Sum, F, Min, Max
from django.forms import TextInput, NumberInput
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView
from django_filters.views import FilterView
from django_tables2 import RequestConfig, MultiTableMixin, SingleTableMixin
from future.backports.urllib.parse import urlencode

from bpp.models import Autor, Cache_Punktacja_Autora_Query, Cache_Punktacja_Autora_Sum, \
    Cache_Punktacja_Autora_Sum_Gruop, Dyscyplina_Naukowa, Cache_Punktacja_Autora_Sum_Ponizej, \
    Cache_Punktacja_Autora_Sum_Group_Ponizej
from bpp.views.mixins import UczelniaSettingRequiredMixin
from django_bpp.version import VERSION
from raport_slotow.forms import AutorRaportSlotowForm, ParametryRaportSlotowUczelniaForm
from raport_slotow.tables import RaportSlotowAutorTable, RaportSlotowUczelniaTable
from raport_slotow.util import create_temporary_table_as, MyExportMixin, MyTableExport, clone_temporary_table, \
    insert_into


class WyborOsoby(UczelniaSettingRequiredMixin, FormView):
    template_name = "raport_slotow/index.html"
    form_class = AutorRaportSlotowForm
    uczelnia_attr = "pokazuj_raport_slotow_autor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Wybór autora'
        return context

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        return HttpResponseRedirect(
            reverse("raport_slotow:raport",
                    kwargs={"autor": form.cleaned_data['obiekt'].slug,
                            "od_roku": form.cleaned_data['od_roku'],
                            "do_roku": form.cleaned_data['do_roku'],
                            }) + "?_export=" + form.cleaned_data['_export']
        )


class RaportSlotow(UczelniaSettingRequiredMixin, MyExportMixin, MultiTableMixin, TemplateView):
    template_name = "raport_slotow/raport_slotow_autor.html"
    table_class = RaportSlotowAutorTable
    uczelnia_attr = "pokazuj_raport_slotow_autor"
    export_formats = ['html', 'xlsx']

    def create_export(self, export_format):
        tables = self.get_tables()
        n = int(self.request.GET.get("n", 0))
        exporter = MyTableExport(
            export_format=export_format,
            table=tables[n],
            export_description=[
                ("Nazwa raportu:", "raport slotów - autor"),
                ("Autor:", str(self.autor)),
                (f"Dyscyplina:", str(tables[n].dyscyplina_naukowa or 'żadna')),
                (f"Od roku:", self.od_roku),
                (f"Do roku:", self.do_roku),
                ("Wygenerowano:", timezone.now()),
                ("Wersja oprogramowania BPP", VERSION)
            ]
        )
        return exporter.response(filename=self.get_export_filename(export_format, n))

    def get_tables(self):
        self.autor = get_object_or_404(Autor, slug=self.kwargs.get("autor"))
        try:
            self.od_roku = int(self.kwargs.get("od_roku"))
            self.do_roku = int(self.kwargs.get("do_roku"))
        except (TypeError, ValueError):
            raise Http404

        cpaq = Cache_Punktacja_Autora_Query.objects.filter(
            autor=self.autor,
            rekord__rok__gte=self.od_roku,
            rekord__rok__lte=self.do_roku,
            pkdaut__gt=0)

        ret = []
        for elem in cpaq.distinct('dyscyplina'):
            table_class = self.get_table_class()
            table = table_class(
                data=cpaq.filter(dyscyplina_id=elem.dyscyplina_id).select_related("rekord", "dyscyplina"))
            RequestConfig(self.request, paginate=self.get_table_pagination(table)).configure(table)
            table.dyscyplina_naukowa = elem.dyscyplina
            ret.append(table)

        if not ret:
            table_class = self.get_table_class()
            table = table_class(data=cpaq.select_related("rekord", "dyscyplina"))
            RequestConfig(self.request, paginate=self.get_table_pagination(table)).configure(table)
            table.dyscyplina_naukowa = None
            ret.append(table)

        return ret

    def get_queryset(self):
        return None

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(RaportSlotow, self).get_context_data(**kwargs)
        context['autor'] = self.autor
        context['od_roku'] = self.od_roku
        context['do_roku'] = self.do_roku
        return context

    def get_export_filename(self, export_format, n):
        return f'raport_slotow_{self.autor.slug}_{self.od_roku}-{self.do_roku}-{n}.{export_format}'

    pass


class ParametryRaportSlotowUczelnia(UczelniaSettingRequiredMixin, FormView):
    template_name = "raport_slotow/index.html"
    form_class = ParametryRaportSlotowUczelniaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Wybór roku'
        return context

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse("raport_slotow:raport-uczelnia") + '?' + urlencode(form.cleaned_data)
        )


class RaportSlotowUczelniaFilter(django_filters.FilterSet):
    autor__nazwisko = django_filters.CharFilter(
        lookup_expr='icontains', widget=TextInput(attrs={'placeholder': 'Podaj nazwisko'}))

    dyscyplina = django_filters.ModelChoiceFilter(queryset=Dyscyplina_Naukowa.objects.all())
    #        lookup_expr='icontains', widget=TextInput(attrs={'placeholder': 'Podaj nazwę dyscypliny'}))

    slot__min = django_filters.NumberFilter(
        "pkdautslotsum", lookup_expr="gte",
        widget=NumberInput(attrs={"placeholder": "min"}))

    slot__max = django_filters.NumberFilter(
        "pkdautslotsum", lookup_expr="lte",
        widget=NumberInput(attrs={"placeholder": "max"}))

    avg__min = django_filters.NumberFilter(
        "avg", lookup_expr="gte",
        widget=NumberInput(attrs={"placeholder": "min"}))

    avg__max = django_filters.NumberFilter(
        "avg", lookup_expr="lte",
        widget=NumberInput(attrs={"placeholder": "max"}))

    class Meta:
        model = Cache_Punktacja_Autora_Sum_Gruop
        fields = ['autor__nazwisko', 'dyscyplina__nazwa']


class RaportSlotowUczelnia(UczelniaSettingRequiredMixin, MyExportMixin, SingleTableMixin, FilterView):
    template_name = "raport_slotow/raport_slotow_uczelnia.html"
    table_class = RaportSlotowUczelniaTable
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ['html', 'xlsx']
    filterset_class = RaportSlotowUczelniaFilter

    def get_table(self, **kwargs):
        table_class = self.get_table_class()
        table = table_class(data=self.get_table_data(), od_roku=self.data['od_roku'], do_roku=self.data['do_roku'],
                            **kwargs)
        RequestConfig(self.request, paginate=self.get_table_pagination(table)).configure(table)
        return table

    def get_export_description(self):
        return [("Nazwa raportu:", "raport slotów - uczelnia"),
                (f"Od roku:", self.data['od_roku']),
                (f"Do roku:", self.data['do_roku']),
                ("Minimalny slot:", self.data['minimalny_slot']),
                ("Uwzględnij autorów poniżej minimalnego slotu:", "tak" if self.data['pokazuj_ponizej'] else "nie"),
                ("Wygenerowano:", timezone.now()),
                ("Wersja oprogramowania BPP", VERSION)]

    def get_form(self, dct):
        return ParametryRaportSlotowUczelniaForm(dct)

    def get(self, request, *args, **kw):
        form = self.get_form(request.GET)

        if form.is_valid():
            self.data = form.cleaned_data
            return super(RaportSlotowUczelnia, self).get(self.request, *args, **kw)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        return HttpResponseRedirect("..")

    def get_context_data(self, *args, **kwargs):
        context = super(RaportSlotowUczelnia, self).get_context_data(**kwargs)
        context.update(self.data)
        context['data'] = self.data
        context['export_link'] = urllib.parse.urlencode(dict(self.request.GET, **{"_export": "xlsx"}), doseq=True)
        return context

    def get_export_filename(self, export_format):
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        return f"raport_dyscyplin_{self.data['od_roku']}-{self.data['do_roku']}_{stamp}.{export_format}"

    def get_queryset(self):
        self.min_slot = self.data['minimalny_slot']

        qset1 = Cache_Punktacja_Autora_Query.objects.filter(
            rekord__rok__gte=self.data['od_roku'],
            rekord__rok__lte=self.data['do_roku'],
            pkdaut__gt=0
        ).annotate(
            pkdautslot=F('pkdaut') / F('slot'),
            pkdautsum=Window(
                expression=Sum('pkdaut'),
                partition_by=[F('autor_id'), F('dyscyplina_id')],
                order_by=[(F('pkdaut') / F('slot')).desc(), "rekord__tytul_oryginalny", ],
            ),
            pkdautslotsum=Window(
                expression=Sum('slot'),
                partition_by=[F('autor_id'), F('dyscyplina_id')],
                order_by=[(F('pkdaut') / F('slot')).desc(), "rekord__tytul_oryginalny", ]
            )
        ).order_by(
            "autor",
            "dyscyplina",
            (F('pkdaut') / F('slot')).desc()
        )

        create_temporary_table_as("bpp_temporary_cpaq", qset1)

        pokazuj_ponizej = self.data['pokazuj_ponizej']

        if pokazuj_ponizej:
            # Stworz klona tabelki wynikowej dla autorów poniżej progu
            clone_temporary_table("bpp_temporary_cpaq", "bpp_temporary_cpaq_2")

        # Usuń wszystkie wyniki mniejsze od poszukiwanego minimalnego slotu
        Cache_Punktacja_Autora_Sum.objects.filter(pkdautslotsum__lt=self.min_slot).delete()

        # Wrzuć do tabeli 'wyjściowej' najmniejsze wartości z tabeli sumowania
        create_temporary_table_as("bpp_temporary_cpasg", Cache_Punktacja_Autora_Sum.objects.values(
            'autor_id', 'dyscyplina_id',
        ).annotate(pkdautslotsum=Min('pkdautslotsum'), pkdautsum=Min('pkdautsum')).order_by())

        if pokazuj_ponizej:
            # Usuń wszystkie wyniki powjżej
            Cache_Punktacja_Autora_Sum_Ponizej.objects.filter(pkdautslotsum__gte=self.min_slot).delete()
            # Wrzuć do tabelki grupowania najwyższe wyniki
            insert_into("bpp_temporary_cpasg", Cache_Punktacja_Autora_Sum_Ponizej.objects.values(
                'autor_id', 'dyscyplina_id',
            ).annotate(pkdautslotsum=Max('pkdautslotsum'), pkdautsum=Max('pkdautsum')).order_by())

            clone_temporary_table("bpp_temporary_cpasg", "bpp_temporary_cpasg_2")
            create_temporary_table_as(
                "bpp_temporary_cpasg",
                Cache_Punktacja_Autora_Sum_Group_Ponizej.objects.values(
                    'autor_id', 'dyscyplina_id'
                ).annotate(pkdautslotsum=Max('pkdautslotsum'), pkdautsum=Max('pkdautsum')).order_by())

        return Cache_Punktacja_Autora_Sum_Gruop.objects.all().annotate(
            avg=F('pkdautsum') / F('pkdautslotsum')
        ).select_related("autor", "dyscyplina")
