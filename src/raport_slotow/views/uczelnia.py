import urllib
from datetime import datetime
from urllib.parse import urlencode

from django.db.models import F, Max, Sum, Window
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import RequestConfig, SingleTableMixin

from bpp.models import (
    Cache_Punktacja_Autora_Query,
    Cache_Punktacja_Autora_Sum,
    Cache_Punktacja_Autora_Sum_Gruop,
)
from bpp.views.mixins import UczelniaSettingRequiredMixin
from django_bpp.version import VERSION
from formdefaults.helpers import FormDefaultsMixin
from raport_slotow.filters import (
    RaportSlotowUczelniaFilter,
    RaportSlotowUczelniaBezJednostekIWydzialowFilter,
)
from raport_slotow.forms import ParametryRaportSlotowUczelniaForm
from raport_slotow.tables import (
    RaportSlotowUczelniaBezJednostekIWydzialowTable,
    RaportSlotowUczelniaTable,
)
from raport_slotow.util import (
    MyExportMixin,
    create_temporary_table_as,
)


class ParametryRaportSlotowUczelnia(
    UczelniaSettingRequiredMixin, FormDefaultsMixin, FormView
):
    template_name = "raport_slotow/index.html"
    form_class = ParametryRaportSlotowUczelniaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - uczelnia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse("raport_slotow:raport-uczelnia")
            + "?"
            + urlencode(form.cleaned_data)
        )


class RaportSlotowUczelnia(
    UczelniaSettingRequiredMixin, MyExportMixin, SingleTableMixin, FilterView
):
    template_name = "raport_slotow/raport_slotow_uczelnia.html"
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]
    filterset_class = RaportSlotowUczelniaFilter

    def get_table_class(self):
        if self.data["dziel_na_jednostki_i_wydzialy"]:
            return RaportSlotowUczelniaTable
        return RaportSlotowUczelniaBezJednostekIWydzialowTable

    def get_filterset_class(self):
        if self.data["dziel_na_jednostki_i_wydzialy"]:
            return RaportSlotowUczelniaFilter
        return RaportSlotowUczelniaBezJednostekIWydzialowFilter

    def get_table(self, **kwargs):
        table_class = self.get_table_class()
        table = table_class(
            data=self.get_table_data(),
            od_roku=self.data["od_roku"],
            do_roku=self.data["do_roku"],
            **kwargs,
        )
        RequestConfig(
            self.request, paginate=self.get_table_pagination(table)
        ).configure(table)
        return table

    def get_export_description(self):
        return [
            ("Nazwa raportu:", "raport slotów - uczelnia"),
            (f"Od roku:", self.data["od_roku"]),
            (f"Do roku:", self.data["do_roku"]),
            ("Maksymalny slot:", self.data["maksymalny_slot"]),
            (
                "Dziel na jednostki:",
                "tak" if self.data["dziel_na_jednostki_i_wydzialy"] else "nie",
            ),
            ("Wygenerowano:", timezone.now()),
            ("Wersja oprogramowania BPP", VERSION),
        ]

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
        context["data"] = self.data
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        return context

    def get_export_filename(self, export_format):
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        return f"raport_dyscyplin_{self.data['od_roku']}-{self.data['do_roku']}_{stamp}.{export_format}"

    def get_queryset(self):
        self.max_slot = self.data["maksymalny_slot"]

        if self.data["dziel_na_jednostki_i_wydzialy"]:
            partition_by = [F("autor_id"), F("jednostka_id"), F("dyscyplina_id")]
            order_by = (
                "autor",
                "jednostka",
                "dyscyplina",
                (F("pkdaut") / F("slot")).desc(),
            )
            group_by = (
                "autor_id",
                "jednostka_id",
                "dyscyplina_id",
            )
            select_related = "autor", "jednostka", "dyscyplina"
        else:
            partition_by = [F("autor_id"), F("dyscyplina_id")]
            order_by = "autor", "dyscyplina", (F("pkdaut") / F("slot")).desc()
            group_by = (
                "autor_id",
                "dyscyplina_id",
            )
            select_related = "autor", "dyscyplina"

        qset1 = (
            Cache_Punktacja_Autora_Query.objects.filter(
                rekord__rok__gte=self.data["od_roku"],
                rekord__rok__lte=self.data["do_roku"],
                pkdaut__gt=0,
            )
            .annotate(
                pkdautslot=F("pkdaut") / F("slot"),
                pkdautsum=Window(
                    expression=Sum("pkdaut"),
                    partition_by=partition_by,
                    order_by=[
                        (F("pkdaut") / F("slot")).desc(),
                        "rekord__tytul_oryginalny",
                    ],
                ),
                pkdautslotsum=Window(
                    expression=Sum("slot"),
                    partition_by=partition_by,
                    order_by=[
                        (F("pkdaut") / F("slot")).desc(),
                        "rekord__tytul_oryginalny",
                    ],
                ),
            )
            .order_by(*order_by)
        )

        create_temporary_table_as("bpp_temporary_cpaq", qset1)

        # Usuń wszystkie wyniki większe od poszukiwanego maksymalnego slotu
        Cache_Punktacja_Autora_Sum.objects.filter(
            pkdautslotsum__gt=self.max_slot
        ).delete()

        # Wrzuć do tabeli 'wyjściowej' największe wartości z tabeli sumowania
        create_temporary_table_as(
            "bpp_temporary_cpasg",
            Cache_Punktacja_Autora_Sum.objects.values(*group_by)
            .annotate(pkdautslotsum=Max("pkdautslotsum"), pkdautsum=Max("pkdautsum"))
            .order_by(),
        )

        if self.data["dziel_na_jednostki_i_wydzialy"] is False:
            from django.db import connection

            cur = connection.cursor()
            cur.execute(
                "ALTER TABLE bpp_temporary_cpasg ADD COLUMN jednostka_id INT DEFAULT NULL;"
            )

        res = (
            Cache_Punktacja_Autora_Sum_Gruop.objects.all()
            .annotate(avg=F("pkdautsum") / F("pkdautslotsum"))
            .select_related(*select_related)
        )

        return res
