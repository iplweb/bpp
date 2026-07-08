import hashlib
import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Count, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.generic import View
from multiseek.logic import get_registry
from multiseek.views import (
    MULTISEEK_SESSION_KEY_REMOVED,
    MultiseekResults,
    manually_add_or_remove,
)

from bpp.models import Uczelnia
from bpp.multiseek_registry import registry as multiseek_registry
from bpp.multiseek_registry.djangoql_export import multiseek_form_to_djangoql
from bpp.views.multiseek_export import (
    MULTISEEK_DEFAULT_REPORT_TITLE,
    MULTISEEK_EXPORT_DANE_FIELDS,
    MULTISEEK_EXPORT_HEADERS,  # noqa: F401 - re-eksport, uzywane w testach
    MULTISEEK_EXPORT_XLSX_HEADERS,  # noqa: F401 - re-eksport, uzywane w testach
    XLSX_WORKSHEET_TITLE_MAX_LENGTH,  # noqa: F401 - re-eksport, uzywane w testach
    csv_export_response,
    plain_multiseek_report_title,
    xlsx_export_response,
)
from bpp.views.zapytanie import WprowadzanieDanychOrSuperuserMixin

logger = logging.getLogger(__name__)

PKT_WEWN = "pkt_wewn"
PKT_WEWN_BEZ = "pkt_wewn_bez"
TABLE = "table"
MULTISEEK_EXPORT_MAX_ROWS = 5000

# TTL cache agregatów wyników (count + sumy) — patrz get_context_data.
MULTISEEK_AGGREGATE_CACHE_TIMEOUT = 30 * 60
MULTISEEK_REPORT_TITLE_SESSION_KEY = "MULTISEEK_TITLE"

EXTRA_TYPES = [
    PKT_WEWN,
    PKT_WEWN_BEZ,
    TABLE,
    PKT_WEWN + "_cytowania",
    PKT_WEWN_BEZ + "_cytowania",
    TABLE + "_cytowania",
]


class MyMultiseekResults(MultiseekResults):
    registry = "bpp.multiseek.registry"

    def get_queryset(self, only_those_ids=None):
        registry = get_registry(self.registry)
        if only_those_ids is not None:
            qset = registry.get_query_for_model(self.get_multiseek_data())
            if not only_those_ids:
                return qset.none()
            qset = qset.filter(pk__in=only_those_ids)
        else:
            qset = super().get_queryset()

        if not self.request.user.is_authenticated:
            uczelnia = Uczelnia.objects.get_for_request(self.request)
            if uczelnia is not None:
                ukryte_statusy = uczelnia.ukryte_statusy("multiwyszukiwarka")
                if ukryte_statusy:
                    qset = qset.exclude(status_korekty_id__in=ukryte_statusy)

        flds = ("id", "opis_bibliograficzny_cache")

        # wycięte z multiseek/views.py, get_context_data
        report_type = registry.get_report_type(
            self.get_multiseek_data(), request=self.request
        )

        if report_type in EXTRA_TYPES:
            qset = qset.select_related("charakter_formalny", "typ_kbn")

            flds = flds + (
                "charakter_formalny",
                "typ_kbn",
                "punkty_kbn",
                "impact_factor",
                "adnotacje",
                "uwagi",
                "punktacja_wewnetrzna",
                "charakter_formalny__nazwa",
                "typ_kbn__nazwa",
                # "zrodlo_lub_nadrzedne",
            )

        ret = qset.only(*flds)

        # Add DISTINCT when joining with views that can produce duplicates.
        # This string-based SQL check is not ideal but avoids complex query
        # introspection. The affected tables come from fulltext search joins.
        sql = str(ret.query)
        if "bpp_autorzy_mat" in sql or "bpp_zewnetrzne_bazy_view" in sql:
            ret = ret.distinct()

        return ret

    def get_queryset_for_current_mode(self):
        if not self.request.GET.get("print-removed", False):
            return self.get_queryset()

        return self.get_queryset(
            only_those_ids=self.request.session.get(MULTISEEK_SESSION_KEY_REMOVED, [])
        )

    def _aggregate_cache_key(self):
        """Klucz cache agregatów wyników (count + sumy) — wszystkie wejścia
        wpływające na wynik: formularz multiseek (z report_type
        i ordering), lista wyrzuconych rekordów, tryb print-removed,
        zalogowanie (ukryte statusy) i uczelnia."""
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        payload = json.dumps(
            [
                self.get_multiseek_data(),
                sorted(str(x) for x in self.get_removed_records()),
                bool(self.request.GET.get("print-removed", False)),
                bool(self.request.user.is_authenticated),
                getattr(uczelnia, "pk", None),
            ],
            sort_keys=True,
            default=str,
        )
        return "multiseek_agregaty:" + hashlib.sha256(payload.encode()).hexdigest()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        qset = self.get_queryset_for_current_mode()
        if self.request.GET.get("print-removed", False):
            ctx["object_list"] = qset
            ctx["print_removed"] = True

        # Agregaty (COUNT + sumy) sa cache'owane, zeby stronicowanie tych
        # samych wynikow nie powtarzalo drogiego skanu (DISTINCT + join do
        # bpp_autorzy_mat) przy kazdej stronie. Staleness ograniczone TTL;
        # kazda zmiana formularza / wyrzucenie rekordu zmienia klucz.
        cache_key = self._aggregate_cache_key()
        agregaty = cache.get(cache_key)
        if agregaty is None:
            if ctx["report_type"] in EXTRA_TYPES:
                # Licznik i sumy jednym skanem — przy DISTINCT + join do
                # bpp_autorzy_mat osobny COUNT podwajalby najdrozsza czesc.
                agregaty = qset.aggregate(
                    Sum("impact_factor"),
                    Sum("liczba_cytowan"),
                    Sum("punkty_kbn"),
                    Sum("index_copernicus"),
                    Sum("punktacja_wewnetrzna"),
                    paginator_count=Count("pk"),
                )
            else:
                agregaty = {"paginator_count": qset.count()}
            cache.set(cache_key, agregaty, MULTISEEK_AGGREGATE_CACHE_TIMEOUT)

        agregaty = dict(agregaty)
        ctx["paginator_count"] = agregaty.pop("paginator_count")
        if ctx["report_type"] in EXTRA_TYPES:
            ctx["sumy"] = agregaty

        ctx["multiseek_export_max_rows"] = MULTISEEK_EXPORT_MAX_ROWS
        object_list = ctx["object_list"]
        object_list.count = lambda *args, **kw: ctx["paginator_count"]

        keys = list(self.request.session.keys())
        if "MULTISEEK_TITLE" not in keys:
            self.request.session["MULTISEEK_TITLE"] = "Rezultat wyszukiwania"
        else:
            if self.request.session["MULTISEEK_TITLE"] == "":
                self.request.session["MULTISEEK_TITLE"] = "Rezultat wyszukiwania"

        return ctx


def _multiseek_report_title(request):
    return plain_multiseek_report_title(
        request.session.get(
            MULTISEEK_REPORT_TITLE_SESSION_KEY,
            MULTISEEK_DEFAULT_REPORT_TITLE,
        )
    )


class MyMultiseekExport(LoginRequiredMixin, MyMultiseekResults):
    http_method_names = ["get"]

    def get(self, request, export_format, *args, **kwargs):
        if export_format not in {"csv", "xlsx"}:
            return HttpResponseBadRequest("Nieznany format eksportu.")

        queryset = self.get_queryset_for_current_mode()
        count = queryset.count()
        if count > MULTISEEK_EXPORT_MAX_ROWS:
            return HttpResponseBadRequest(
                "Eksport Multiseek jest dostępny dla maksymalnie "
                f"{MULTISEEK_EXPORT_MAX_ROWS} rekordów."
            )

        report_title = _multiseek_report_title(request)
        queryset = queryset.select_related(None).only(*MULTISEEK_EXPORT_DANE_FIELDS)
        if export_format == "csv":
            return csv_export_response(queryset, request, report_title)
        return xlsx_export_response(queryset, request, report_title)


def _normalize_session_removed(request):
    # JSONSerializer zamienia tuple → list przy zapisie sesji. Upstream
    # manually_add_or_remove() robi `set(data)` na odczycie, co pada na
    # listach (unhashable). Konwertujemy z powrotem do tuple w pamięci —
    # w ramach tego requestu upstream zobaczy tuple; serializacja z
    # powrotem do listy nastąpi przy zapisie sesji.
    data = request.session.get(MULTISEEK_SESSION_KEY_REMOVED)
    if not data:
        return
    normalized = [tuple(x) if isinstance(x, list) else x for x in data]
    if normalized != data:
        request.session[MULTISEEK_SESSION_KEY_REMOVED] = normalized


@never_cache
def bpp_remove_by_hand(request, pk):
    """Add a record's PK to a list of manually removed records.

    User, via the web ui, can add or remove a record to a list of records
    removed "by hand". Those records will be explictly removed
    from the search results in the query function. The list of those
    records is cleaned when there is a form reset.
    """
    pk = tuple(int(x) for x in pk.split("_"))
    _normalize_session_removed(request)
    return manually_add_or_remove(request, pk)


@never_cache
def bpp_remove_from_removed_by_hand(request, pk):
    """Cancel manual record removal."""
    pk = tuple(int(x) for x in pk.split("_"))
    _normalize_session_removed(request)
    return manually_add_or_remove(request, pk, add=False)


class MultiseekToDjangoQLView(WprowadzanieDanychOrSuperuserMixin, View):
    """Tlumaczy biezacy formularz Multiseek (POST 'json') na zapytanie
    DjangoQL nad Rekord. Zwraca {query, warnings, editor_url}."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        raw = request.POST.get("json")
        if not raw:
            return HttpResponseBadRequest("Brak parametru 'json'.")
        try:
            form_json = json.loads(raw)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Niepoprawny JSON formularza.")
        if not isinstance(form_json, dict):
            return HttpResponseBadRequest("Oczekiwano obiektu JSON.")
        try:
            result = multiseek_form_to_djangoql(form_json, multiseek_registry)
        except (KeyError, TypeError, AttributeError):
            logger.exception(
                "Niepoprawna struktura formularza przesłana do MultiseekToDjangoQLView."
            )
            return HttpResponseBadRequest("Niepoprawna struktura formularza.")
        return JsonResponse(
            {
                "query": result.query,
                "warnings": result.warnings,
                "editor_url": result.editor_url,
            }
        )
