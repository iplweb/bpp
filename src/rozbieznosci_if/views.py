from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from braces.views import GroupRequiredMixin
from celery.result import AsyncResult
from django import forms
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from openpyxl import Workbook

from bpp.models import Wydawnictwo_Ciagle
from bpp.util import worksheet_columns_autosize, worksheet_create_table
from rozbieznosci_if.models import IgnorujRozbieznoscIf, RozbieznosciIfLog

CURRENT_YEAR = datetime.now().year
DEFAULT_ROK_OD = 2022
OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20
DEFAULT_SORT = "-ostatnio_zmieniony"


class SetForm(forms.Form):
    _set = forms.IntegerField(min_value=0)


class IgnoreForm(forms.Form):
    _ignore = forms.IntegerField(min_value=0)


class FilterForm(forms.Form):
    rok_od = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    tytul = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w tytule..."}),
    )

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or CURRENT_YEAR

    def clean_tytul(self):
        return self.cleaned_data.get("tytul") or ""


def get_valid_sort_fields_for_field(field_name):
    """Return valid sort fields for a given field name."""
    annotated_field = f"punktacja_zrodla_{field_name}"
    return [
        "rok",
        "-rok",
        field_name,
        f"-{field_name}",
        annotated_field,
        f"-{annotated_field}",
        "ostatnio_zmieniony",
        "-ostatnio_zmieniony",
    ]


# IF-specific sort fields (for backwards compatibility)
VALID_SORT_FIELDS = get_valid_sort_fields_for_field("impact_factor")


def get_base_queryset_for_field(field_name, ignore_model):
    """
    Return base queryset for discrepancies for a given field.

    Args:
        field_name: The field to compare (e.g., "impact_factor" or "punkty_kbn")
        ignore_model: The model class for ignored records

    Returns queryset of Wydawnictwo_Ciagle with discrepancies.
    """
    annotated_field = f"punktacja_zrodla_{field_name}"
    return (
        Wydawnictwo_Ciagle.objects.exclude(zrodlo=None)
        .filter(zrodlo__punktacja_zrodla__rok=F("rok"))
        .exclude(**{f"zrodlo__punktacja_zrodla__{field_name}": F(field_name)})
        .exclude(
            pk__in=ignore_model.objects.filter(
                content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
            ).values_list("object_id")
        )
        .select_related("zrodlo")
        .annotate(**{annotated_field: F(f"zrodlo__punktacja_zrodla__{field_name}")})
    )


def get_base_queryset():
    """Return base queryset for IF discrepancies (backwards compatible wrapper)."""
    return get_base_queryset_for_field("impact_factor", IgnorujRozbieznoscIf)


def apply_filters(queryset, rok_od, rok_do, tytul=""):
    """Apply year range and title filter to queryset."""
    queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)
    if tytul:
        queryset = queryset.filter(tytul_oryginalny__icontains=tytul)
    return queryset


def apply_sorting(queryset, sort_field, valid_sort_fields=None):
    """Apply sorting to queryset."""
    if valid_sort_fields is None:
        valid_sort_fields = VALID_SORT_FIELDS
    if sort_field in valid_sort_fields:
        return queryset.order_by(sort_field)
    return queryset.order_by(DEFAULT_SORT)


def build_redirect_url(url_name, rok_od, rok_do, tytul=""):
    """Build redirect URL with filter parameters."""
    url = reverse(url_name)
    params = []
    if rok_od != DEFAULT_ROK_OD:
        params.append(f"rok_od={rok_od}")
    if rok_do != CURRENT_YEAR:
        params.append(f"rok_do={rok_do}")
    if tytul:
        params.append(f"tytul={quote(tytul)}")
    if params:
        url += "?" + "&".join(params)
    return HttpResponseRedirect(url)


class BaseRozbieznosciView(GroupRequiredMixin, ListView):
    """Base view for discrepancy lists - can be configured for different fields."""

    group_required = "wprowadzanie danych"
    paginate_by = 25

    # Subclasses must define these
    template_name = None
    field_name = None  # e.g., "impact_factor" or "punkty_kbn"
    field_label = None  # e.g., "IF" or "punkty MNiSW"
    ignore_model = None  # e.g., IgnorujRozbieznoscIf
    log_model = None  # e.g., RozbieznosciIfLog
    log_before_field = None  # e.g., "if_before" or "pk_before"
    log_after_field = None  # e.g., "if_after" or "pk_after"
    app_name = None  # e.g., "rozbieznosci_if"
    page_title = None  # e.g., "Rozbieżności IF"
    panel_class = ""  # e.g., "" or "pk-panel"

    def get_valid_sort_fields(self):
        return get_valid_sort_fields_for_field(self.field_name)

    def get_filter_params(self):
        """Get filter parameters from request."""
        form = FilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            tytul = form.cleaned_data["tytul"]
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = CURRENT_YEAR
            tytul = ""

        valid_sort_fields = self.get_valid_sort_fields()
        sort = self.request.GET.get("sort", DEFAULT_SORT)
        if sort not in valid_sort_fields:
            sort = DEFAULT_SORT

        return rok_od, rok_do, tytul, sort

    def get_queryset(self):
        rok_od, rok_do, tytul, sort = self.get_filter_params()

        queryset = get_base_queryset_for_field(self.field_name, self.ignore_model)
        queryset = apply_filters(queryset, rok_od, rok_do, tytul)
        queryset = apply_sorting(queryset, sort, self.get_valid_sort_fields())

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rok_od, rok_do, tytul, sort = self.get_filter_params()

        context["rok_od"] = rok_od
        context["rok_do"] = rok_do
        context["tytul"] = tytul
        context["current_sort"] = sort

        # Field-specific context for templates
        context["page_title"] = self.page_title
        context["panel_class"] = self.panel_class
        context["field_name"] = self.field_name
        context["field_label"] = self.field_label
        context["field_label_pracy"] = f"{self.field_label} pracy"
        context["field_label_zrodla"] = f"{self.field_label} źródła"
        context["sort_field"] = self.field_name
        context["sort_field_desc"] = f"-{self.field_name}"
        context["sort_field_zrodla"] = f"punktacja_zrodla_{self.field_name}"
        context["sort_field_zrodla_desc"] = f"-punktacja_zrodla_{self.field_name}"
        context["app_name"] = self.app_name

        # Build query string without sort parameter for column headers
        query_params = []
        if rok_od != DEFAULT_ROK_OD:
            query_params.append(f"rok_od={rok_od}")
        if rok_do != CURRENT_YEAR:
            query_params.append(f"rok_do={rok_do}")
        if tytul:
            query_params.append(f"tytul={quote(tytul)}")
        context["filter_query_string"] = "&".join(query_params)

        return context

    def _handle_ignore(self, request):
        """Handle _ignore parameter - add record to ignored list."""
        frm = IgnoreForm(request.GET)
        if not frm.is_valid():
            return

        pk = frm.cleaned_data["_ignore"]
        _, created = self.ignore_model.objects.get_or_create(
            object_id=pk,
            content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        )
        if created:
            try:
                wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
                messages.info(
                    request,
                    f'Rekord "{wc.tytul_oryginalny}" (ID: {pk}) został dodany '
                    f"do listy ignorowanych.",
                )
            except Wydawnictwo_Ciagle.DoesNotExist:
                messages.info(
                    request,
                    f"Rekord (ID: {pk}) został dodany do listy ignorowanych.",
                )
        else:
            messages.warning(
                request, f"Rekord (ID: {pk}) był już na liście ignorowanych."
            )

    def _handle_set(self, request):
        """Handle _set parameter - update field from source."""
        frm = SetForm(request.GET)
        if not frm.is_valid():
            return

        pk = frm.cleaned_data["_set"]
        self.ignore_model.objects.filter(
            object_id=pk,
            content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        ).delete()

        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
            punktacja = wc.punktacja_zrodla()
            old_value = getattr(wc, self.field_name)
            new_value = getattr(punktacja, self.field_name) if punktacja else None
            if punktacja and old_value != new_value:
                setattr(wc, self.field_name, new_value)
                wc.save()

                # Recalculate cache if this is a scoring field
                if self.field_name == "punkty_kbn":
                    wc.przelicz_punkty_dyscyplin()

                # Log the change
                self.log_model.objects.create(
                    rekord=wc,
                    zrodlo=wc.zrodlo,
                    **{
                        self.log_before_field: old_value,
                        self.log_after_field: new_value,
                    },
                    user=request.user,
                )

                messages.success(
                    request,
                    f'Rekord "{wc.tytul_oryginalny}" (ID: {pk}): '
                    f"{self.field_label} zmieniony z {old_value} na {new_value}.",
                )
            else:
                messages.info(
                    request,
                    f'Rekord "{wc.tytul_oryginalny}" (ID: {pk}): '
                    f"{self.field_label} nie wymagał zmiany.",
                )
        except Wydawnictwo_Ciagle.DoesNotExist:
            messages.error(request, f"Rekord (ID: {pk}) nie został znaleziony.")

    def get(self, request, *args, **kw):
        if "_ignore" in request.GET:
            self._handle_ignore(request)

        if "_set" in request.GET:
            self._handle_set(request)

        return super().get(request, *args, **kw)


class RozbieznosciView(BaseRozbieznosciView):
    """IF discrepancies view."""

    template_name = "rozbieznosci_if/index.html"
    field_name = "impact_factor"
    field_label = "IF"
    ignore_model = IgnorujRozbieznoscIf
    log_model = RozbieznosciIfLog
    log_before_field = "if_before"
    log_after_field = "if_after"
    app_name = "rozbieznosci_if"
    page_title = "Rozbieżności IF"
    panel_class = ""


class BaseRozbieznosciExportView(GroupRequiredMixin, View):
    """Base class for exporting discrepancies to XLSX."""

    group_required = "wprowadzanie danych"

    # Subclasses must define these
    field_name = None
    field_label = None
    ignore_model = None
    sheet_title = None
    filename_prefix = None
    table_title = None

    def get_valid_sort_fields(self):
        return get_valid_sort_fields_for_field(self.field_name)

    def get_filter_params(self):
        """Get filter parameters from request."""
        form = FilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            tytul = form.cleaned_data["tytul"]
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = CURRENT_YEAR
            tytul = ""

        valid_sort_fields = self.get_valid_sort_fields()
        sort = self.request.GET.get("sort", DEFAULT_SORT)
        if sort not in valid_sort_fields:
            sort = DEFAULT_SORT

        return rok_od, rok_do, tytul, sort

    def get(self, request):
        rok_od, rok_do, tytul, sort = self.get_filter_params()

        queryset = get_base_queryset_for_field(self.field_name, self.ignore_model)
        queryset = apply_filters(queryset, rok_od, rok_do, tytul)
        queryset = apply_sorting(queryset, sort, self.get_valid_sort_fields())

        wb = Workbook()
        ws = wb.active
        ws.title = self.sheet_title

        # Headers
        annotated_field = f"punktacja_zrodla_{self.field_name}"
        headers = [
            "Tytuł",
            "Rok",
            "Źródło",
            f"{self.field_label} pracy",
            f"{self.field_label} źródła",
            "Ostatnio zmieniony",
        ]
        ws.append(headers)

        # Data
        for elem in queryset:
            field_value = getattr(elem, self.field_name)
            field_value_zrodla = getattr(elem, annotated_field)
            ws.append(
                [
                    elem.tytul_oryginalny,
                    elem.rok,
                    elem.zrodlo.nazwa if elem.zrodlo else "",
                    float(field_value) if field_value else 0,
                    float(field_value_zrodla) if field_value_zrodla else 0,
                    elem.ostatnio_zmieniony.strftime("%Y-%m-%d %H:%M")
                    if elem.ostatnio_zmieniony
                    else "",
                ]
            )

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title=self.table_title)

        # Create response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"{self.filename_prefix}_{rok_od}_{rok_do}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response


class RozbieznosciExportView(BaseRozbieznosciExportView):
    """Export IF discrepancies to XLSX."""

    field_name = "impact_factor"
    field_label = "IF"
    ignore_model = IgnorujRozbieznoscIf
    sheet_title = "Rozbieżności IF"
    filename_prefix = "rozbieznosci_if"
    table_title = "RozbieznosciIF"


def ustaw_pole_ze_zrodla(
    pks, field_name, log_model, log_before_field, log_after_field, user_id=None
):
    """
    Update a field for publications from their source.

    Args:
        pks: List of publication primary keys to update.
        field_name: Name of the field to update (e.g., "impact_factor" or "punkty_kbn")
        log_model: Model class for logging changes
        log_before_field: Field name for storing old value in log
        log_after_field: Field name for storing new value in log
        user_id: Optional user ID for logging purposes.

    Returns tuple (updated_count, error_count).
    """
    from bpp.models import BppUser

    updated = 0
    errors = 0

    # Get user object if user_id provided
    user = None
    if user_id:
        try:
            user = BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            pass

    for pk in pks:
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
            punktacja = wc.punktacja_zrodla()
            old_value = getattr(wc, field_name)
            new_value = getattr(punktacja, field_name) if punktacja else None
            if punktacja and old_value != new_value:
                setattr(wc, field_name, new_value)
                wc.save()

                # Recalculate cache if this is a scoring field
                if field_name == "punkty_kbn":
                    wc.przelicz_punkty_dyscyplin()

                # Log the change
                log_model.objects.create(
                    rekord=wc,
                    zrodlo=wc.zrodlo,
                    **{log_before_field: old_value, log_after_field: new_value},
                    user=user,
                )

                updated += 1
        except (Wydawnictwo_Ciagle.DoesNotExist, Exception):
            errors += 1

    return updated, errors


def ustaw_if_ze_zrodla(pks, user_id=None):
    """Update impact_factor for publications (backwards compatible wrapper)."""
    return ustaw_pole_ze_zrodla(
        pks, "impact_factor", RozbieznosciIfLog, "if_before", "if_after", user_id
    )


class BaseUstawWszystkieView(GroupRequiredMixin, View):
    """Base class for bulk update views."""

    group_required = "wprowadzanie danych"

    # Subclasses must define these
    field_name = None
    field_label = None
    ignore_model = None
    log_model = None
    log_before_field = None
    log_after_field = None
    app_name = None
    celery_task = (
        None  # String path like "rozbieznosci_if.tasks.task_ustaw_if_ze_zrodla"
    )

    def get_filter_params(self):
        """Get filter parameters from request."""
        form = FilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            tytul = form.cleaned_data["tytul"]
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = CURRENT_YEAR
            tytul = ""

        return rok_od, rok_do, tytul

    def get_celery_task(self):
        """Return the Celery task to use for async processing."""
        raise NotImplementedError("Subclasses must implement get_celery_task")

    def get(self, request):
        rok_od, rok_do, tytul = self.get_filter_params()

        queryset = get_base_queryset_for_field(self.field_name, self.ignore_model)
        queryset = apply_filters(queryset, rok_od, rok_do, tytul)

        pks = list(queryset.values_list("pk", flat=True))
        count = len(pks)

        if count == 0:
            messages.warning(
                request,
                f"Nie znaleziono rekordów z rozbieżnymi wartościami {self.field_label} "
                f"do aktualizacji.",
            )
            return self._redirect_back(rok_od, rok_do, tytul)

        if count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            task = self.get_celery_task().delay(pks, user_id=request.user.id)
            return redirect(f"{self.app_name}:task_status", task_id=task.id)
        else:
            updated, errors = ustaw_pole_ze_zrodla(
                pks,
                self.field_name,
                self.log_model,
                self.log_before_field,
                self.log_after_field,
                user_id=request.user.id,
            )
            if errors:
                messages.warning(
                    request,
                    f"Zaktualizowano {updated} rekordów. Wystąpiły błędy dla {errors} rekordów.",
                )
            else:
                messages.success(request, f"Zaktualizowano {updated} rekordów.")

            return self._redirect_back(rok_od, rok_do, tytul)

    def _redirect_back(self, rok_od, rok_do, tytul=""):
        return build_redirect_url(f"{self.app_name}:index", rok_od, rok_do, tytul)


class UstawWszystkieView(BaseUstawWszystkieView):
    """Set IF from source for all filtered records."""

    field_name = "impact_factor"
    field_label = "IF"
    ignore_model = IgnorujRozbieznoscIf
    log_model = RozbieznosciIfLog
    log_before_field = "if_before"
    log_after_field = "if_after"
    app_name = "rozbieznosci_if"

    def get_celery_task(self):
        from rozbieznosci_if.tasks import task_ustaw_if_ze_zrodla

        return task_ustaw_if_ze_zrodla


class BaseTaskStatusView(GroupRequiredMixin, View):
    """Base class for task status views with HTMX polling."""

    group_required = "wprowadzanie danych"

    # Subclasses must define these
    app_name = None
    template_name = None
    progress_template_name = None
    page_title = None

    def get(self, request, task_id):
        task = AsyncResult(task_id)
        task_info = task.info if isinstance(task.info, dict) else {}

        context = {
            "task_id": task_id,
            "task_ready": task.ready(),
            "page_title": self.page_title,
            "app_name": self.app_name,
        }

        if not task.ready():
            # Task in progress
            context["info"] = task_info

        elif task.failed():
            # Task failed
            context["error"] = str(task.info)

        elif task.successful():
            # Task done - redirect back
            result = task.result
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)
            pbn_queued = result.get("pbn_queued", 0)

            if pbn_queued:
                messages.success(
                    request,
                    f"Zaktualizowano {updated} rekordów i dodano {pbn_queued} "
                    f"do kolejki wysyłki do PBN."
                    + (f" Błędy: {errors}." if errors else ""),
                )
            else:
                messages.success(
                    request,
                    f"Zaktualizowano {updated} rekordów."
                    + (f" Błędy: {errors}." if errors else ""),
                )

            # HTMX redirect
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = reverse(f"{self.app_name}:index")
                return response
            return redirect(f"{self.app_name}:index")

        # HTMX request: return partial only
        if request.headers.get("HX-Request"):
            return render(request, self.progress_template_name, context)

        return render(request, self.template_name, context)


class TaskStatusView(BaseTaskStatusView):
    """Display IF task progress with HTMX polling."""

    app_name = "rozbieznosci_if"
    template_name = "rozbieznosci_if/task_status.html"
    progress_template_name = "rozbieznosci_if/_progress.html"
    page_title = "Rozbieżności IF"
