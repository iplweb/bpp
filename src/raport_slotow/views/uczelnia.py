import urllib

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import ListView
from django_filters.views import FilterMixin
from django_tables2 import RequestConfig, SingleTableMixin
from formdefaults.helpers import FormDefaultsMixin
from liveops.views import CreateLiveOperationView, RestartView

from bpp.views.mixins import UczelniaSettingRequiredMixin
from django_bpp.version import VERSION
from nowe_raporty.views import BaseRaportAuthMixin
from raport_slotow.filters import (
    RaportSlotowUczelniaBezJednostekIWydzialowFilter,
    RaportSlotowUczelniaFilter,
)
from raport_slotow.forms.uczelnia import UtworzRaportSlotowUczelniaForm
from raport_slotow.models.uczelnia import RaportSlotowUczelnia
from raport_slotow.tables import (
    RaportSlotowUczelniaBezJednostekIWydzialowTable,
    RaportSlotowUczelniaTable,
)
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu
from raport_slotow.util import MyExportMixin

# Stany terminalne liveops — restart/regen dozwolony TYLKO w nich (guard §8.4).
_STANY_TERMINALNE = ("FINISHED_OK", "FINISHED_ERROR", "CANCELLED")


class _LiveopsNoPermissionCompatMixin:
    """Ujednolica sygnaturę ``handle_no_permission`` przy łączeniu naszych
    braces-owych mixinów (``UczelniaSettingRequiredMixin`` → braces
    ``AccessMixin``) z liveops ``BaseLiveOperationMixin`` (Django ``AccessMixin``).

    liveops woła ``self.handle_no_permission()`` BEZ argumentu (Django-style),
    a braces wymaga ``request`` — kolizja w MRO (braces wygrywa, bo jest
    wcześniej) → ``TypeError`` dla niezalogowanego. Nadpisujemy metodą
    tolerującą oba wywołania i zawsze przekierowującą na login (raise_exception
    domyślnie False → redirect, jak w legacy)."""

    def handle_no_permission(self, request=None):
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )


class ListaRaportSlotowUczelnia(BaseRaportAuthMixin, FormDefaultsMixin, ListView):
    """Lista raportów bieżącego użytkownika (owner-scoped).

    Dawniej long_running.LongRunningOperationsView (który dodatkowo KASOWAŁ
    stare operacje > 10). Teraz zwykły owner-scoped ListView — housekeeping to
    nie zadanie list-view. Strona live/postępu jest osobno, pod centralnym
    ``liveops:live`` (link przez ``object.get_absolute_url``).
    """

    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - uczelnia"
    model = RaportSlotowUczelnia

    def get_queryset(self):
        return RaportSlotowUczelnia.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class UtworzRaportSlotowUczelnia(
    _LiveopsNoPermissionCompatMixin,
    UczelniaSettingRequiredMixin,
    FormDefaultsMixin,
    CreateLiveOperationView,
):
    template_name = "raport_slotow/index.html"
    form_class = UtworzRaportSlotowUczelniaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - uczelnia"
    model = RaportSlotowUczelnia

    def form_valid(self, form):
        # Scoping per-uczelnia (§8.1): łapiemy uczelnię z requestu (host →
        # Site → Uczelnia; superuser może nadpisać ?uczelnia=) i utrwalamy PRZED
        # save() — generacja biegnie w tle (bez requestu). Enqueue bezpośrednio
        # (bez on_commit): tworzenie nie jest w atomic i brak ATOMIC_REQUESTS.
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.uczelnia = uczelnia_dla_odczytu(self.request)
        self.object.save()
        self.object.enqueue()
        return redirect(self.object.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class WygenerujPonownieRaportSlotowUczelnia(
    _LiveopsNoPermissionCompatMixin, BaseRaportAuthMixin, RestartView
):
    """Regeneracja raportu (POST-only, jak liveops RestartView).

    URL ma tylko ``pk`` (bez ``op_type``), więc nadpisujemy ``get_object``
    i rozwiązujemy model wprost, owner-scoped. Bramka: ``BaseRaportAuthMixin``
    (grupa GR_RAPORTY_WYSWIETLANIE + owner-scope) — liveops REQUIRED_GROUP nie
    jest ustawione, więc sam liveops NIE gejtuje.

    Guard „reset tylko gdy skończone" (§8.4): liveops RestartView resetuje
    BEZWARUNKOWO (on_restart kasuje wiersze + re-enqueue). Raport slotów nie ma
    maszyny stanów, więc regen w połowie runu skasowałby wiersze, które biegnący
    task jeszcze pisze. Resetujemy WYŁĄCZNIE gdy stan terminalny.
    """

    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    model = RaportSlotowUczelnia

    def get_object(self, queryset=None):
        return get_object_or_404(
            RaportSlotowUczelnia, pk=self.kwargs["pk"], owner=self.request.user
        )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.get_state() not in _STANY_TERMINALNE:
            # Nie-skończony raport (biegnie / nie wystartował) — nic nie rób,
            # tylko wróć na stronę live (jak legacy „reset tylko gdy finished").
            return redirect(obj.get_absolute_url())
        return super().post(request, *args, **kwargs)


class SzczegolyRaportSlotowUczelniaListaRekordow(
    BaseRaportAuthMixin,
    LoginRequiredMixin,
    MyExportMixin,
    SingleTableMixin,
    ListView,
    FilterMixin,
):
    template_name = "raport_slotow/raport_slotow_uczelnia.html"
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]
    filterset_class = RaportSlotowUczelniaFilter
    model = RaportSlotowUczelnia
    paginate_by = 25

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(RaportSlotowUczelnia, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def get_table_class(self):
        if self.parent_object.dziel_na_jednostki_i_wydzialy:
            return RaportSlotowUczelniaTable
        return RaportSlotowUczelniaBezJednostekIWydzialowTable

    def get_filterset_class(self):
        if self.parent_object.dziel_na_jednostki_i_wydzialy:
            return RaportSlotowUczelniaFilter
        return RaportSlotowUczelniaBezJednostekIWydzialowFilter

    def get_table(self, **kwargs):
        table_class = self.get_table_class()
        table = table_class(
            data=self.get_table_data(),
            od_roku=self.parent_object.od_roku,
            do_roku=self.parent_object.do_roku,
            slot=self.parent_object.slot,
            **kwargs,
        )
        RequestConfig(
            self.request, paginate=self.get_table_pagination(table)
        ).configure(table)
        return table

    def get_export_description(self):
        wygenerowano = "(brak danych)"
        if self.parent_object.finished_on:
            wygenerowano = timezone.make_naive(self.parent_object.finished_on)

        return [
            ("Nazwa raportu:", "raport slotów - uczelnia"),
            ("Od roku:", self.parent_object.od_roku),
            ("Do roku:", self.parent_object.do_roku),
            ("Maksymalny slot:", self.parent_object.slot),
            (
                "Dziel na jednostki:",
                "tak" if self.parent_object.dziel_na_jednostki_i_wydzialy else "nie",
            ),
            ("Wygenerowano:", wygenerowano),
            ("Wersja oprogramowania BPP", VERSION),
        ]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.parent_object
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        context["filter"] = self.get_filterset(self.get_filterset_class())
        return context

    def get_export_filename(self, export_format):
        stamp = timezone.now().strftime("%Y%m%d-%H%M")
        return f"raport_dyscyplin_{self.parent_object.od_roku}-{self.parent_object.do_roku}_{stamp}.{export_format}"

    def get(self, *args, **kw):
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)

        if (
            not self.filterset.is_bound
            or self.filterset.is_valid()
            or not self.get_strict()
        ):
            self.object_list = self.filterset.qs
        else:
            self.object_list = self.filterset.queryset.none()

        self.table_data = self.object_list

        return super().get(*args, **kw)
