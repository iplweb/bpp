from io import BytesIO
from typing import NamedTuple

from braces.views import GroupRequiredMixin
from celery.result import AsyncResult
from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views import View
from django.views.generic import ListView
from openpyxl import Workbook

from bpp.models import Charakter_Formalny, Uczelnia, Wydawnictwo_Ciagle
from bpp.util import worksheet_columns_autosize, worksheet_create_table
from bpp.util.uczelnia_scope import tylko_jedna_uczelnia
from rozbieznosci.core import (
    DEFAULT_SORT,
    DEFAULT_TRYB_ZRODLA,
    apply_filters,
    apply_sorting,
    get_base_queryset_for_metryka,
    get_valid_sort_fields,
    ustaw_ze_zrodla,
)
from rozbieznosci.forms import (
    CURRENT_YEAR,
    DEFAULT_ROK_OD,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
    TRYB_ZRODLA_CHOICES,
    FilterForm,
    IgnoreForm,
    SetForm,
)
from rozbieznosci.metryki import METRYKI, METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc


class Filtry(NamedTuple):
    rok_od: int
    rok_do: int
    tytul: str
    sort: str
    tryb_zrodla: str
    kasuj_przy_pustym: bool
    charaktery: list


class MetrykaMixin:
    group_required = "wprowadzanie danych"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.metryka = METRYKI_BY_SLUG.get(kwargs.get("metryka"))
        if self.metryka is None:
            raise Http404("Nieznana metryka")


def _filter_params(source, metryka):
    form = FilterForm(source)
    if form.is_valid():
        rok_od = form.cleaned_data["rok_od"]
        rok_do = form.cleaned_data["rok_do"]
        tytul = form.cleaned_data["tytul"]
        tryb = form.cleaned_data["tryb_zrodla"]
        kasuj = form.cleaned_data["kasuj_przy_pustym_zrodle"]
        charaktery = list(form.cleaned_data["charaktery_formalne"])
    else:
        rok_od, rok_do, tytul = DEFAULT_ROK_OD, CURRENT_YEAR, ""
        tryb, kasuj, charaktery = DEFAULT_TRYB_ZRODLA, False, []
    sort = source.get("sort", DEFAULT_SORT)
    if sort not in get_valid_sort_fields(metryka):
        sort = DEFAULT_SORT
    return Filtry(rok_od, rok_do, tytul, sort, tryb, kasuj, charaktery)


def _query_string(f):
    params = {}
    if f.rok_od != DEFAULT_ROK_OD:
        params["rok_od"] = f.rok_od
    if f.rok_do != CURRENT_YEAR:
        params["rok_do"] = f.rok_do
    if f.tytul:
        params["tytul"] = f.tytul
    if f.tryb_zrodla != DEFAULT_TRYB_ZRODLA:
        params["tryb_zrodla"] = f.tryb_zrodla
    if f.kasuj_przy_pustym:
        params["kasuj_przy_pustym_zrodle"] = "1"
    if f.charaktery:
        params["charaktery_formalne"] = [c.pk for c in f.charaktery]
    return urlencode(params, doseq=True)


def _scope_do_uczelni(qs, request):
    """Zawęź queryset rozbieżności do uczelni oglądającej (multi-hosted).

    Queryset to ``Wydawnictwo_Ciagle`` (rekord), więc atrybucja przez
    ``autorzy_set__jednostka__uczelnia`` — reguła wspólna ze stroną główną
    (``scope_rekord_do_uczelni``): rekord należy do uczelni, gdy którakolwiek
    jednostka zapisana na autorstwie należy do tej uczelni.

    No-op (zwraca ten sam qs) gdy brak mapowania Site→Uczelnia (fail-open, jak
    ``scope_rekord_do_uczelni``) albo gdy w systemie jest jedna uczelnia
    (guard ``tylko_jedna_uczelnia`` — single-host = brak zawężenia).
    """
    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(autorzy_set__jednostka__uczelnia=uczelnia).distinct()


class RozbieznosciView(MetrykaMixin, GroupRequiredMixin, ListView):
    template_name = "rozbieznosci/index.html"
    paginate_by = 25

    def get_queryset(self):
        f = _filter_params(self.request.GET, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, tryb_zrodla=f.tryb_zrodla)
        qs = apply_filters(qs, f.rok_od, f.rok_do, f.tytul, f.charaktery)
        qs = apply_sorting(qs, f.sort, self.metryka)
        qs = _scope_do_uczelni(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        f = _filter_params(self.request.GET, self.metryka)
        field = self.metryka.field_name
        context.update(
            {
                "metryka": self.metryka,
                "metryki": METRYKI,
                "page_title": f"Rozbieżności: {self.metryka.label}",
                "rok_od": f.rok_od,
                "rok_do": f.rok_do,
                "tytul": f.tytul,
                "current_sort": f.sort,
                "tryb_zrodla": f.tryb_zrodla,
                "tryb_zrodla_choices": TRYB_ZRODLA_CHOICES,
                "kasuj_przy_pustym_zrodle": f.kasuj_przy_pustym,
                "wszystkie_charaktery": Charakter_Formalny.objects.order_by("nazwa"),
                "wybrane_charaktery_ids": [c.pk for c in f.charaktery],
                "charaktery_zawezone": bool(f.charaktery),
                "field_name": field,
                "field_label": self.metryka.label,
                "annotated_field": f"punktacja_zrodla_{field}",
                "sort_field": field,
                "sort_field_desc": f"-{field}",
                "sort_field_zrodla": f"punktacja_zrodla_{field}",
                "sort_field_zrodla_desc": f"-punktacja_zrodla_{field}",
                "filter_query_string": _query_string(f),
            }
        )
        return context

    def _handle_ignore(self, request):
        frm = IgnoreForm(request.POST)
        if not frm.is_valid():
            return
        pk = frm.cleaned_data["_ignore"]
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
        except Wydawnictwo_Ciagle.DoesNotExist:
            messages.error(request, f"Rekord (ID: {pk}) nie istnieje.")
            return
        _, created = IgnorowanaRozbieznosc.objects.get_or_create(
            metryka=self.metryka.slug, rekord=wc
        )
        if created:
            messages.info(
                request,
                f'Rekord "{wc.tytul_oryginalny}" (ID: {pk}) dodany do '
                f"ignorowanych ({self.metryka.label}).",
            )
        else:
            messages.warning(request, f"Rekord (ID: {pk}) był już ignorowany.")

    def _handle_set(self, request):
        frm = SetForm(request.POST)
        if not frm.is_valid():
            return
        pk = frm.cleaned_data["_set"]
        f = _filter_params(request.POST, self.metryka)
        IgnorowanaRozbieznosc.objects.filter(
            metryka=self.metryka.slug, rekord_id=pk
        ).delete()
        updated, errors = ustaw_ze_zrodla(
            [pk],
            self.metryka,
            user_id=request.user.id,
            kasuj_przy_pustym=f.kasuj_przy_pustym,
        )
        if updated:
            messages.success(
                request,
                f"Rekord (ID: {pk}): {self.metryka.label} ustawiony wg źródła.",
            )
        elif errors:
            messages.error(request, f"Rekord (ID: {pk}): błąd aktualizacji.")
        else:
            messages.info(
                request,
                f"Rekord (ID: {pk}): pominięty — źródło nie ma wartości "
                f"{self.metryka.label} za dany rok (zaznacz „kasuj…”, aby "
                f"wyczyścić wartość w pracy).",
            )

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if "_set" in request.POST:
            self._handle_set(request)
        if "_ignore" in request.POST:
            self._handle_ignore(request)
        f = _filter_params(request.POST, self.metryka)
        url = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
        qs = _query_string(f)
        if f.sort != DEFAULT_SORT:
            qs = f"{qs}&sort={f.sort}" if qs else f"sort={f.sort}"
        target_url = f"{url}?{qs}" if qs else url
        if not url_has_allowed_host_and_scheme(
            url=target_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            target_url = url
        return HttpResponseRedirect(target_url)


class RozbieznosciExportView(MetrykaMixin, GroupRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        f = _filter_params(request.GET, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, tryb_zrodla=f.tryb_zrodla)
        qs = apply_filters(qs, f.rok_od, f.rok_do, f.tytul, f.charaktery)
        qs = apply_sorting(qs, f.sort, self.metryka)
        qs = _scope_do_uczelni(qs, request)

        field = self.metryka.field_name
        annotated = f"punktacja_zrodla_{field}"
        label = self.metryka.label

        wb = Workbook()
        ws = wb.active
        ws.title = label[:31]
        ws.append(
            [
                "Tytuł",
                "Rok",
                f"{label} pracy",
                "Źródło",
                f"{label} źródła",
            ]
        )
        for elem in qs:
            v = getattr(elem, field)
            vz = getattr(elem, annotated)
            if elem.zrodlo_ma_wpis:
                wartosc_zrodla = float(vz) if vz else 0
            else:
                wartosc_zrodla = f"brak wpisu za {elem.rok}"
            ws.append(
                [
                    elem.tytul_oryginalny,
                    elem.rok,
                    float(v) if v else 0,
                    elem.zrodlo.nazwa if elem.zrodlo else "",
                    wartosc_zrodla,
                ]
            )

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title=f"Rozbieznosci_{self.metryka.slug}")

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        filename = f"rozbieznosci_{self.metryka.slug}_{f.rok_od}_{f.rok_do}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        vb = BytesIO()
        wb.save(vb)
        vb.seek(0)
        response.write(vb.getvalue())
        return response


def _komunikat_wynik(request, updated, errors, skipped):
    """Spójny komunikat po akcji ustawiania: zaktualizowano/pominięto/błędy."""
    msg = f"Zaktualizowano {updated} rekordów."
    if skipped:
        msg += f" Pominięto {skipped} (źródło bez wartości za dany rok)."
    if errors:
        msg += f" Błędy: {errors}."
    (messages.warning if errors else messages.success)(request, msg)


class UstawWszystkieView(MetrykaMixin, GroupRequiredMixin, View):
    confirm_template_name = "rozbieznosci/ustaw_wszystkie_confirm.html"

    def _redirect_back(self, f):
        url = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
        qs = _query_string(f)
        target_url = f"{url}?{qs}" if qs else url
        if not url_has_allowed_host_and_scheme(
            url=target_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            target_url = url
        return HttpResponseRedirect(target_url)

    def get(self, request, *args, **kwargs):
        f = _filter_params(request.GET, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, tryb_zrodla=f.tryb_zrodla)
        qs = apply_filters(qs, f.rok_od, f.rok_do, f.tytul, f.charaktery)
        qs = _scope_do_uczelni(qs, request)
        count = qs.count()
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(f)
        return render(
            request,
            self.confirm_template_name,
            {
                "metryka": self.metryka,
                "rok_od": f.rok_od,
                "rok_do": f.rok_do,
                "tytul": f.tytul,
                "tryb_zrodla": f.tryb_zrodla,
                "kasuj_przy_pustym_zrodle": f.kasuj_przy_pustym,
                "wybrane_charaktery_ids": [c.pk for c in f.charaktery],
                "count": count,
                "field_label": self.metryka.label,
                "use_celery": count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
                "filter_query_string": _query_string(f),
            },
        )

    def post(self, request, *args, **kwargs):
        f = _filter_params(request.POST, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, tryb_zrodla=f.tryb_zrodla)
        qs = apply_filters(qs, f.rok_od, f.rok_do, f.tytul, f.charaktery)
        qs = _scope_do_uczelni(qs, request)
        pks = list(qs.values_list("pk", flat=True))
        count = len(pks)
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(f)
        if count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            from rozbieznosci.tasks import task_ustaw_ze_zrodla

            task = task_ustaw_ze_zrodla.delay(
                pks,
                self.metryka.slug,
                user_id=request.user.id,
                kasuj_przy_pustym=f.kasuj_przy_pustym,
            )
            return redirect(
                reverse(
                    "rozbieznosci:task_status",
                    kwargs={
                        "metryka": self.metryka.slug,
                        "task_id": task.id,
                    },
                )
            )
        updated, errors = ustaw_ze_zrodla(
            pks,
            self.metryka,
            user_id=request.user.id,
            kasuj_przy_pustym=f.kasuj_przy_pustym,
        )
        _komunikat_wynik(request, updated, errors, count - updated - errors)
        return self._redirect_back(f)


class TaskStatusView(MetrykaMixin, GroupRequiredMixin, View):
    template_name = "rozbieznosci/task_status.html"
    progress_template_name = "rozbieznosci/_progress.html"

    def get(self, request, metryka, task_id):
        task = AsyncResult(task_id)
        task_ready = task.ready()
        info = task.info if isinstance(task.info, dict) else {}
        context = {
            "metryka": self.metryka,
            "task_id": task_id,
            "task_ready": task_ready,
            "page_title": f"Rozbieżności: {self.metryka.label}",
        }
        if not task_ready:
            context["info"] = info
        elif task.failed():
            context["error"] = str(task.info)
        elif task.successful():
            result = task.result
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)
            total = result.get("total", updated + errors)
            _komunikat_wynik(request, updated, errors, total - updated - errors)
            index = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
            if request.headers.get("HX-Request"):
                resp = HttpResponse(status=200)
                resp["HX-Redirect"] = index
                return resp
            return redirect(index)
        if request.headers.get("HX-Request"):
            return render(request, self.progress_template_name, context)
        return render(request, self.template_name, context)
