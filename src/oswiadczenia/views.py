from io import BytesIO
from urllib.parse import quote

from braces.views import GroupRequiredMixin
from django import forms
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView
from django_sendfile import sendfile
from openpyxl import Workbook

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autorzy,
    Cache_Punktacja_Autora,
    Dyscyplina_Naukowa,
    Rekord,
)
from bpp.util import worksheet_columns_autosize, worksheet_create_table

DEFAULT_ROK_OD = 2022
DEFAULT_ROK_DO = 2025
EXPORT_CHUNK_SIZE = 5000


class WydrukOswiadczenFilterForm(forms.Form):
    rok_od = forms.IntegerField(
        min_value=2022,
        max_value=2025,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=2022,
        max_value=2025,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    szukaj_autor = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj autora..."}),
    )
    szukaj_tytul = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj tytulu..."}),
    )
    dyscyplina = forms.ModelChoiceField(
        queryset=Dyscyplina_Naukowa.objects.all(),
        required=False,
        empty_label="-- wszystkie dyscypliny --",
    )

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or DEFAULT_ROK_DO

    def clean_szukaj_autor(self):
        return self.cleaned_data.get("szukaj_autor") or ""

    def clean_szukaj_tytul(self):
        return self.cleaned_data.get("szukaj_tytul") or ""


def get_base_queryset():
    """Return base queryset for declarations (Autorzy with discipline assigned)."""
    return (
        Autorzy.objects.exclude(dyscyplina_naukowa=None)
        .filter(rekord__rok__gte=DEFAULT_ROK_OD, rekord__rok__lte=DEFAULT_ROK_DO)
        .select_related("autor", "rekord", "dyscyplina_naukowa")
        .order_by("rekord__rok", "autor__nazwisko", "autor__imiona")
    )


def apply_filters(
    queryset, rok_od, rok_do, szukaj_autor="", szukaj_tytul="", dyscyplina=None
):
    """Apply filters to queryset."""
    queryset = queryset.filter(rekord__rok__gte=rok_od, rekord__rok__lte=rok_do)
    if szukaj_autor:
        queryset = queryset.filter(
            Q(autor__nazwisko__icontains=szukaj_autor)
            | Q(autor__imiona__icontains=szukaj_autor)
        )
    if szukaj_tytul:
        queryset = queryset.filter(rekord__tytul_oryginalny__icontains=szukaj_tytul)
    if dyscyplina:
        queryset = queryset.filter(dyscyplina_naukowa=dyscyplina)
    return queryset


def calculate_export_ranges(total_count: int, chunk_size: int = EXPORT_CHUNK_SIZE):
    """Calculate export ranges for pagination.

    Returns list of tuples: [(start, end, label), ...]
    """
    if total_count <= chunk_size:
        return []

    ranges = []
    start = 0
    while start < total_count:
        end = min(start + chunk_size, total_count)
        label = f"{start + 1}-{end}"
        ranges.append((start, end, label))
        start = end
    return ranges


def get_autor_dyscyplina_info(autor, rok):
    """Check if author has alternative discipline for given year."""
    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
        return {
            "ma_dwie_dyscypliny": ad.dwie_dyscypliny(),
            "dyscyplina_naukowa": ad.dyscyplina_naukowa,
            "subdyscyplina_naukowa": ad.subdyscyplina_naukowa,
        }
    except Autor_Dyscyplina.DoesNotExist:
        return {
            "ma_dwie_dyscypliny": False,
            "dyscyplina_naukowa": None,
            "subdyscyplina_naukowa": None,
        }


class WydrukOswiadczen2022View(GroupRequiredMixin, ListView):
    """Main list view for declaration printing 2022-2025."""

    template_name = "oswiadczenia/wydruk_oswiadczen_2022_25.html"
    group_required = "wprowadzanie danych"
    paginate_by = 25

    def get_filter_params(self):
        """Get filter parameters from request."""
        form = WydrukOswiadczenFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            szukaj_autor = form.cleaned_data["szukaj_autor"]
            szukaj_tytul = form.cleaned_data["szukaj_tytul"]
            dyscyplina = form.cleaned_data.get("dyscyplina")
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = DEFAULT_ROK_DO
            szukaj_autor = ""
            szukaj_tytul = ""
            dyscyplina = None
        return rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina

    def get_queryset(self):
        rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina = (
            self.get_filter_params()
        )
        return apply_filters(
            get_base_queryset(), rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina = (
            self.get_filter_params()
        )

        context["rok_od"] = rok_od
        context["rok_do"] = rok_do
        context["szukaj_autor"] = szukaj_autor
        context["szukaj_tytul"] = szukaj_tytul
        context["dyscyplina"] = dyscyplina
        context["dyscypliny"] = (
            Dyscyplina_Naukowa.objects.filter(
                autorzy__rekord__rok__gte=DEFAULT_ROK_OD,
                autorzy__rekord__rok__lte=DEFAULT_ROK_DO,
            )
            .distinct()
            .order_by("nazwa")
        )

        # Build query string for export links
        query_params = []
        if rok_od != DEFAULT_ROK_OD:
            query_params.append(f"rok_od={rok_od}")
        if rok_do != DEFAULT_ROK_DO:
            query_params.append(f"rok_do={rok_do}")
        if szukaj_autor:
            query_params.append(f"szukaj_autor={quote(szukaj_autor)}")
        if szukaj_tytul:
            query_params.append(f"szukaj_tytul={quote(szukaj_tytul)}")
        if dyscyplina:
            query_params.append(f"dyscyplina={dyscyplina.pk}")
        context["filter_query_string"] = "&".join(query_params)

        # Calculate export ranges for chunked exports
        total_count = context["page_obj"].paginator.count
        context["export_ranges"] = calculate_export_ranges(total_count)
        context["export_chunk_size"] = EXPORT_CHUNK_SIZE

        # Precompute alternative discipline info for each entry
        autor_dyscypliny_cache = {}
        for entry in context["object_list"]:
            cache_key = (entry.autor_id, entry.rekord.rok)
            if cache_key not in autor_dyscypliny_cache:
                autor_dyscypliny_cache[cache_key] = get_autor_dyscyplina_info(
                    entry.autor, entry.rekord.rok
                )
            entry.autor_dyscyplina_info = autor_dyscypliny_cache[cache_key]

        return context


class OswiadczenieAutoraView(GroupRequiredMixin, DetailView):
    template_name = "oswiadczenia/oswiadczenie_autora.html"
    group_required = "wprowadzanie danych"

    def get_object(self, queryset=None):
        try:
            self.object = Rekord.objects.get(
                pk=(self.kwargs["content_type_id"], self.kwargs["object_id"])
            )
        except Rekord.DoesNotExist:
            raise Http404 from None

        try:
            autorzy_entry = self.object.autorzy_set.get(
                autor_id=self.kwargs["autor_id"]
            )
            self.autor = autorzy_entry.autor
            self.data_oswiadczenia = autorzy_entry.data_oswiadczenia
            self.przypieta = autorzy_entry.przypieta
        except Autor.DoesNotExist:
            raise Http404 from None

        try:
            self.dyscyplina_pracy = Dyscyplina_Naukowa.objects.get(
                pk=self.kwargs["dyscyplina_pracy_id"]
            )
        except Dyscyplina_Naukowa.DoesNotExist:
            raise NotImplementedError from None

        try:
            self.dyscyplina_naukowa = Autor_Dyscyplina.objects.get(
                rok=self.object.rok, autor=self.autor
            ).dyscyplina_naukowa
        except Autor_Dyscyplina.DoesNotExist:
            self.dyscyplina_naukowa = None

        try:
            self.subdyscyplina_naukowa = Autor_Dyscyplina.objects.get(
                rok=self.object.rok, autor=self.autor
            ).subdyscyplina_naukowa
        except Autor_Dyscyplina.DoesNotExist:
            self.subdyscyplina_naukowa = None

        return self.object

    def get_context_data(self, **kwargs):
        return {
            "object": self.object,
            "autor": self.autor,
            "dyscyplina_pracy": self.dyscyplina_pracy,
            "dyscyplina_naukowa": self.dyscyplina_naukowa,
            "subdyscyplina_naukowa": self.subdyscyplina_naukowa,
            "data_oswiadczenia": self.data_oswiadczenia,
            "przypieta": self.przypieta,
        }


class OswiadczenieAutoraAlternatywnaDyscyplinaView(OswiadczenieAutoraView):
    def get_context_data(self, **kwargs):
        # Ustaw alternatywną dyscyplinę, czyli nie tą która jest przy pracy
        if self.dyscyplina_pracy == self.dyscyplina_naukowa:
            self.dyscyplina_pracy = self.subdyscyplina_naukowa
        else:
            self.dyscyplina_pracy = self.dyscyplina_naukowa

        return super().get_context_data(**kwargs)


class OswiadczeniaPublikacji(GroupRequiredMixin, DetailView):
    template_name = "oswiadczenia/wiele_oswiadczen.html"
    group_required = "wprowadzanie danych"

    def get_object(self, **kwargs):
        try:
            self.object = Rekord.objects.get(
                pk=(self.kwargs["content_type_id"], self.kwargs["object_id"])
            )
        except Rekord.DoesNotExist:
            raise Http404 from None

        return self.object

    def get_context_data(self, **kwargs):
        return {
            "object": self.object,
            "punktacje": Cache_Punktacja_Autora.objects.filter(
                rekord_id=self.object.pk
            ),
        }


class WydrukOswiadczenExportView(GroupRequiredMixin, View):
    """Export declarations to XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Get filter parameters from request."""
        form = WydrukOswiadczenFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            szukaj_autor = form.cleaned_data["szukaj_autor"]
            szukaj_tytul = form.cleaned_data["szukaj_tytul"]
            dyscyplina = form.cleaned_data.get("dyscyplina")
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = DEFAULT_ROK_DO
            szukaj_autor = ""
            szukaj_tytul = ""
            dyscyplina = None
        return rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina

    def get(self, request):
        rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina = (
            self.get_filter_params()
        )

        queryset = get_base_queryset()
        queryset = apply_filters(
            queryset, rok_od, rok_do, szukaj_autor, szukaj_tytul, dyscyplina
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Oświadczenia 2022-25"

        # Headers
        headers = [
            "Rok",
            "Autor",
            "Dyscyplina",
            "Przypięta",
            "Alt. dyscyplina",
            "Opis bibliograficzny",
        ]
        ws.append(headers)

        # Cache for author discipline info
        autor_dyscypliny_cache = {}

        # Data
        for entry in queryset:
            # Get alternative discipline info
            cache_key = (entry.autor_id, entry.rekord.rok)
            if cache_key not in autor_dyscypliny_cache:
                autor_dyscypliny_cache[cache_key] = get_autor_dyscyplina_info(
                    entry.autor, entry.rekord.rok
                )
            ad_info = autor_dyscypliny_cache[cache_key]

            alt_dyscyplina = ""
            if ad_info["ma_dwie_dyscypliny"]:
                if entry.dyscyplina_naukowa == ad_info["dyscyplina_naukowa"]:
                    alt_dyscyplina = (
                        str(ad_info["subdyscyplina_naukowa"])
                        if ad_info["subdyscyplina_naukowa"]
                        else ""
                    )
                else:
                    alt_dyscyplina = (
                        str(ad_info["dyscyplina_naukowa"])
                        if ad_info["dyscyplina_naukowa"]
                        else ""
                    )

            ws.append(
                [
                    entry.rekord.rok,
                    str(entry.autor),
                    str(entry.dyscyplina_naukowa) if entry.dyscyplina_naukowa else "",
                    "tak" if entry.przypieta else "nie",
                    alt_dyscyplina,
                    entry.rekord.opis_bibliograficzny_cache,
                ]
            )

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title="Oswiadczenia2022_25")

        # Create response
        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        filename = f"oswiadczenia_{rok_od}_{rok_do}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response


class StartExportTaskView(GroupRequiredMixin, View):
    """Start a background export task."""

    group_required = "wprowadzanie danych"

    def post(self, request):
        from oswiadczenia.models import OswiadczeniaExportTask
        from oswiadczenia.tasks import generate_oswiadczenia_zip

        export_format = request.POST.get("format", "html")

        # Get filter params from GET (query string)
        form = WydrukOswiadczenFilterForm(request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            szukaj_autor = form.cleaned_data["szukaj_autor"]
            szukaj_tytul = form.cleaned_data["szukaj_tytul"]
            dyscyplina = form.cleaned_data.get("dyscyplina")
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = DEFAULT_ROK_DO
            szukaj_autor = ""
            szukaj_tytul = ""
            dyscyplina = None

        # Get offset and limit for chunked exports
        try:
            offset = int(request.GET.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.GET.get("limit", EXPORT_CHUNK_SIZE))
        except (ValueError, TypeError):
            limit = EXPORT_CHUNK_SIZE

        # Create task record
        task = OswiadczeniaExportTask.objects.create(
            user=request.user,
            export_format=export_format,
            rok_od=rok_od,
            rok_do=rok_do,
            szukaj_autor=szukaj_autor,
            szukaj_tytul=szukaj_tytul,
            dyscyplina_id=dyscyplina.pk if dyscyplina else None,
            offset=offset,
            limit=limit,
        )

        # Start Celery task
        generate_oswiadczenia_zip.delay(task.pk)

        return redirect("oswiadczenia:task-status", task_id=task.pk)


class TaskStatusView(GroupRequiredMixin, View):
    """Display task progress with HTMX polling."""

    group_required = "wprowadzanie danych"

    def get(self, request, task_id):
        from oswiadczenia.models import OswiadczeniaExportTask

        task = get_object_or_404(OswiadczeniaExportTask, pk=task_id, user=request.user)

        context = {"task": task}

        # HTMX request: return partial only
        if request.headers.get("HX-Request"):
            return render(request, "oswiadczenia/_progress.html", context)

        return render(request, "oswiadczenia/task_status.html", context)


class DownloadResultView(GroupRequiredMixin, View):
    """Download the generated ZIP file."""

    group_required = "wprowadzanie danych"

    def get(self, request, task_id):
        from oswiadczenia.models import OswiadczeniaExportTask

        task = get_object_or_404(
            OswiadczeniaExportTask, pk=task_id, user=request.user, status="completed"
        )

        if not task.result_file:
            raise Http404("File not found")

        filename = task.result_file.name.split("/")[-1]
        return sendfile(
            request,
            task.result_file.path,
            attachment=True,
            attachment_filename=filename,
        )
