from urllib.parse import quote

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import Http404
from django.views.generic import ListView

from bpp.models import Wydawnictwo_Ciagle
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
    params = []
    if rok_od != DEFAULT_ROK_OD:
        params.append(f"rok_od={rok_od}")
    if rok_do != CURRENT_YEAR:
        params.append(f"rok_do={rok_do}")
    if tytul:
        params.append(f"tytul={quote(tytul)}")
    if pokaz:
        params.append("pokaz_puste_zrodla=1")
    return "&".join(params)


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
        frm = IgnoreForm(request.GET)
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
        frm = SetForm(request.GET)
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
        if "_ignore" in request.GET:
            self._handle_ignore(request)
        if "_set" in request.GET:
            self._handle_set(request)
        return super().get(request, *args, **kwargs)
