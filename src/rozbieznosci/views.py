from io import BytesIO

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

from bpp.models import Wydawnictwo_Ciagle
from bpp.util import worksheet_columns_autosize, worksheet_create_table
from rozbieznosci.core import (
    DEFAULT_SORT,
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
    FilterForm,
    IgnoreForm,
    SetForm,
)
from rozbieznosci.metryki import METRYKI, METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc


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
        pokaz = form.cleaned_data["pokaz_puste_zrodla"]
    else:
        rok_od, rok_do, tytul, pokaz = DEFAULT_ROK_OD, CURRENT_YEAR, "", False
    sort = source.get("sort", DEFAULT_SORT)
    if sort not in get_valid_sort_fields(metryka):
        sort = DEFAULT_SORT
    return rok_od, rok_do, tytul, sort, pokaz


def _query_string(rok_od, rok_do, tytul, pokaz):
    params = {}
    if rok_od != DEFAULT_ROK_OD:
        params["rok_od"] = rok_od
    if rok_do != CURRENT_YEAR:
        params["rok_do"] = rok_do
    if tytul:
        params["tytul"] = tytul
    if pokaz:
        params["pokaz_puste_zrodla"] = "1"
    return urlencode(params)


class RozbieznosciView(MetrykaMixin, GroupRequiredMixin, ListView):
    template_name = "rozbieznosci/index.html"
    paginate_by = 25

    def get_queryset(self):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            self.request.GET, self.metryka
        )
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        qs = apply_sorting(qs, sort, self.metryka)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            self.request.GET, self.metryka
        )
        field = self.metryka.field_name
        context.update(
            {
                "metryka": self.metryka,
                "metryki": METRYKI,
                "page_title": f"Rozbieżności: {self.metryka.label}",
                "rok_od": rok_od,
                "rok_do": rok_do,
                "tytul": tytul,
                "current_sort": sort,
                "pokaz_puste_zrodla": pokaz,
                "field_name": field,
                "field_label": self.metryka.label,
                "annotated_field": f"punktacja_zrodla_{field}",
                "sort_field": field,
                "sort_field_desc": f"-{field}",
                "sort_field_zrodla": f"punktacja_zrodla_{field}",
                "sort_field_zrodla_desc": f"-punktacja_zrodla_{field}",
                "filter_query_string": _query_string(rok_od, rok_do, tytul, pokaz),
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
        IgnorowanaRozbieznosc.objects.filter(
            metryka=self.metryka.slug, rekord_id=pk
        ).delete()
        updated, errors = ustaw_ze_zrodla([pk], self.metryka, user_id=request.user.id)
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
                f"Rekord (ID: {pk}): {self.metryka.label} bez zmian.",
            )

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if "_set" in request.POST:
            self._handle_set(request)
        if "_ignore" in request.POST:
            self._handle_ignore(request)
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(request.POST, self.metryka)
        url = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
        qs = _query_string(rok_od, rok_do, tytul, pokaz)
        if sort != DEFAULT_SORT:
            qs = f"{qs}&sort={sort}" if qs else f"sort={sort}"
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
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(request.GET, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        qs = apply_sorting(qs, sort, self.metryka)

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
                "Źródło",
                f"{label} pracy",
                f"{label} źródła",
                "Ostatnio zmieniony",
            ]
        )
        for elem in qs:
            v = getattr(elem, field)
            vz = getattr(elem, annotated)
            ws.append(
                [
                    elem.tytul_oryginalny,
                    elem.rok,
                    elem.zrodlo.nazwa if elem.zrodlo else "",
                    float(v) if v else 0,
                    float(vz) if vz else 0,
                    (
                        elem.ostatnio_zmieniony.strftime("%Y-%m-%d %H:%M")
                        if elem.ostatnio_zmieniony
                        else ""
                    ),
                ]
            )

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title=f"Rozbieznosci_{self.metryka.slug}")

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        filename = f"rozbieznosci_{self.metryka.slug}_{rok_od}_{rok_do}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        vb = BytesIO()
        wb.save(vb)
        vb.seek(0)
        response.write(vb.getvalue())
        return response


class UstawWszystkieView(MetrykaMixin, GroupRequiredMixin, View):
    confirm_template_name = "rozbieznosci/ustaw_wszystkie_confirm.html"

    def _redirect_back(self, rok_od, rok_do, tytul, pokaz):
        url = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
        qs = _query_string(rok_od, rok_do, tytul, pokaz)
        target_url = f"{url}?{qs}" if qs else url
        if not url_has_allowed_host_and_scheme(
            url=target_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            target_url = url
        return HttpResponseRedirect(target_url)

    def get(self, request, *args, **kwargs):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(request.GET, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        count = qs.count()
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(rok_od, rok_do, tytul, pokaz)
        return render(
            request,
            self.confirm_template_name,
            {
                "metryka": self.metryka,
                "rok_od": rok_od,
                "rok_do": rok_do,
                "tytul": tytul,
                "pokaz_puste_zrodla": pokaz,
                "count": count,
                "field_label": self.metryka.label,
                "use_celery": count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
            },
        )

    def post(self, request, *args, **kwargs):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(request.POST, self.metryka)
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        pks = list(qs.values_list("pk", flat=True))
        count = len(pks)
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(rok_od, rok_do, tytul, pokaz)
        if count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            from rozbieznosci.tasks import task_ustaw_ze_zrodla

            task = task_ustaw_ze_zrodla.delay(
                pks, self.metryka.slug, user_id=request.user.id
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
        updated, errors = ustaw_ze_zrodla(pks, self.metryka, user_id=request.user.id)
        if errors:
            messages.warning(request, f"Zaktualizowano {updated}. Błędy: {errors}.")
        else:
            messages.success(request, f"Zaktualizowano {updated} rekordów.")
        return self._redirect_back(rok_od, rok_do, tytul, pokaz)


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
            messages.success(
                request,
                f"Zaktualizowano {updated} rekordów."
                + (f" Błędy: {errors}." if errors else ""),
            )
            index = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
            if request.headers.get("HX-Request"):
                resp = HttpResponse(status=200)
                resp["HX-Redirect"] = index
                return resp
            return redirect(index)
        if request.headers.get("HX-Request"):
            return render(request, self.progress_template_name, context)
        return render(request, self.template_name, context)
