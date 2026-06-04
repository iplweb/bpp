from django.db.utils import OperationalError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, View

from bpp.models import Autor, Uczelnia

from .queries import (
    MAKS_GLEBOKOSC_FILTR,
    MIN_PRAC_ZRODLO,
    STATEMENT_TIMEOUT_FILTR_MS,
    Filtr,
    _autor_dict,
    _autorzy_widocznej_sieci,
    _bfs_siec,
    _filtr_z_request,
    _int_or_none,
    _int_param,
    _krawedzie_wewnatrz,
    _limit_czasu,
    _metryki_prac,
    _pbn_root,
    _sasiedzi_authorconnection,
    _sasiedzi_cache,
    _uczelnia_zatrudnienia,
    _zakres_lat,
    siec_powiazan_wlaczona,
)


class GrafPowiazanView(TemplateView):
    """Strona z interaktywnym grafem powiązań autora."""

    template_name = "powiazania_autorow/graf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        autor = get_object_or_404(Autor, pk=kwargs["pk"])
        if not siec_powiazan_wlaczona(autor, self.request):
            raise Http404("Sieć powiązań jest wyłączona dla tego autora.")
        context["autor"] = autor
        return context


class GrafPowiazan3DView(TemplateView):
    """Widok 3D sieci powiązań (Three.js / WebGL) — alternatywa dla 2D.

    Czyta ten sam endpoint danych (siec.json) co widok 2D; różni się tylko
    rendererem po stronie klienta. Bramkowany tym samym ustawieniem
    "pokazuj sieć powiązań" (404 gdy wyłączone).
    """

    template_name = "powiazania_autorow/graf3d.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        autor = get_object_or_404(Autor, pk=kwargs["pk"])
        if not siec_powiazan_wlaczona(autor, self.request):
            raise Http404("Sieć powiązań jest wyłączona dla tego autora.")
        context["autor"] = autor
        return context


class GrafPowiazanDaneView(View):
    """JSON z sąsiadami (współautorami) danego autora.

    Ten sam endpoint obsługuje węzeł centralny i każde rozwinięcie po stronie
    klienta. Sąsiedzi filtrowani do pokazuj=True, sortowani malejąco po liczbie
    wspólnych publikacji. Każdy autor (centrum i sąsiad) niesie tytuł naukowy,
    ORCID i URL do PBN — UI buduje z tego tooltip i menu akcji.
    """

    def get(self, request, pk):
        autor = get_object_or_404(Autor.objects.select_related("tytul"), pk=pk)
        if not siec_powiazan_wlaczona(autor, request):
            raise Http404("Sieć powiązań jest wyłączona dla tego autora.")
        pbn_root = _pbn_root(Uczelnia.objects.get_for_request(request))
        filtr = _filtr_z_request(request)
        uczelnia_zatr = _uczelnia_zatrudnienia(request)

        if filtr.aktywny():
            # liczenie z cache (self-join) pod twardym statement_timeout —
            # patologiczny filtr ubija własny request, nie bazę
            try:
                with _limit_czasu(STATEMENT_TIMEOUT_FILTR_MS):
                    wybrani = _sasiedzi_cache(autor, filtr, uczelnia_zatr)
            except OperationalError:
                return JsonResponse(
                    {
                        "error": "Zapytanie z filtrem trwało za długo — "
                        "zawęź zakres lat lub liczbę źródeł."
                    },
                    status=503,
                )
        else:
            wybrani = _sasiedzi_authorconnection(autor, uczelnia_zatr)

        metryki = _metryki_prac([autor.pk] + [a.pk for a, _ in wybrani])

        neighbors = [
            _autor_dict(a, pbn_root, shared=s, metryki=metryki.get(a.pk))
            for a, s in wybrani
        ]

        return JsonResponse(
            {
                "center": _autor_dict(autor, pbn_root, metryki=metryki.get(autor.pk)),
                "neighbors": neighbors,
            }
        )


class GrafPowiazanSiecView(View):
    """Cała pod-sieć powiązań do zadanej głębokości (BFS) w jednym żądaniu.

    Pozwala pokazać "wianuszek" na N poziomów bez klikania węzeł po węźle (co
    od strony przeglądarki oznaczałoby setki round-tripów). BFS po precomputed
    AuthorConnection: na każdym poziomie bierzemy top-N najsilniejszych
    (najwięcej wspólnych publikacji) widocznych sąsiadów każdego węzła frontu.
    Twardy limit MAKS_WEZLOW_SIECI chroni przed eksplozją depth × rozgałęzienie.

    Każdy węzeł niesie poziom BFS i id rodzica — UI układa z tego zagnieżdżone
    pączki (dzieci wokół rodzica). Krawędzie to relacje rodzic→dziecko (drzewo
    rozwijania), więc widok pozostaje czytelny nawet przy dużej głębokości.
    """

    def get(self, request, pk):
        autor = get_object_or_404(Autor, pk=pk)
        if not siec_powiazan_wlaczona(autor, request):
            raise Http404("Sieć powiązań jest wyłączona dla tego autora.")
        depth = _int_param(request, "depth", 2, 1, 10)
        topn = _int_param(request, "topn", 15, 1, 50)
        filtr = _filtr_z_request(request)
        uczelnia_zatr = _uczelnia_zatrudnienia(request)
        if filtr.aktywny():
            # przy liczeniu z cache tniemy głębokość (self-join jest droższy)
            depth = min(depth, MAKS_GLEBOKOSC_FILTR)

        if filtr.aktywny():
            # BFS i krawędzie poprzeczne liczone z cache (self-join) pod
            # twardym statement_timeout — patologiczna gęsta sieć ubija własny
            # request (503), zamiast męczyć bazę
            try:
                with _limit_czasu(STATEMENT_TIMEOUT_FILTR_MS):
                    level_of, parent_of, krawedzie, przyciecie = _bfs_siec(
                        autor.pk, depth, topn, filtr, uczelnia_zatr
                    )
                    visited = set(level_of.keys())
                    extra_edges = _krawedzie_wewnatrz(visited, krawedzie, filtr)
            except OperationalError:
                return JsonResponse(
                    {
                        "error": "Zapytanie z filtrem trwało za długo — "
                        "zawęź zakres lat lub liczbę źródeł."
                    },
                    status=503,
                )
        else:
            level_of, parent_of, krawedzie, przyciecie = _bfs_siec(
                autor.pk, depth, topn, filtr, uczelnia_zatr
            )
            visited = set(level_of.keys())
            # Krawędzie "poprzeczne": wszystkie powiązania MIĘDZY widocznymi
            # autorami, których nie ma w drzewie rozwijania. UI pokazuje je na
            # żądanie (przełącznik), żeby zobaczyć powiązania wewnątrz grupy bez
            # klikania każdego autora.
            extra_edges = _krawedzie_wewnatrz(visited, krawedzie, filtr)

        autorzy = {
            a.pk: a
            for a in Autor.objects.filter(id__in=visited).select_related("tytul")
        }
        pbn_root = _pbn_root(Uczelnia.objects.get_for_request(request))
        metryki = _metryki_prac(list(visited))

        nodes = []
        for aid in visited:
            a = autorzy.get(aid)
            if a is None:
                continue
            dane = _autor_dict(a, pbn_root, metryki=metryki.get(aid))
            dane["level"] = level_of[aid]
            dane["parent"] = parent_of[aid]
            nodes.append(dane)

        edges = [{"source": a, "target": b, "shared": sh} for a, b, sh in krawedzie]

        rok_min, rok_max = _zakres_lat(autor.pk)

        return JsonResponse(
            {
                "center_id": autor.pk,
                "nodes": nodes,
                "edges": edges,
                "extra_edges": extra_edges,
                "truncated": przyciecie,
                "rok_min": rok_min,
                "rok_max": rok_max,
            }
        )


class GrafPowiazanZrodlaView(View):
    """Lista źródeł i wydawców prac CAŁEJ widocznej sieci (z filtrem roku).

    Zasila combobox "pokazuj tylko prace z:" — każda pozycja z liczbą prac,
    np. "Blood (500)". Zbiór autorów = ta sama sieć BFS co graf (depth/topn +
    rok + zatrudnieni), więc zmiana tych kontrolek realnie zmienia listę.
    Filtr źródła/wydawcy świadomie pomijamy przy liczeniu zbioru autorów — w
    przeciwnym razie wybór źródła zawężałby sieć, a ta listę (sprzężenie).

    Dwa GROUP BY na cache (bpp_autorzy_mat ⋈ bpp_rekord_mat) po pracach
    widocznych autorów; `Count(DISTINCT rekord)` liczy każdą pracę raz, nawet
    gdy współautorzy z sieci dzielą ją między sobą.
    """

    def get(self, request, pk):
        autor = get_object_or_404(Autor, pk=pk)
        if not siec_powiazan_wlaczona(autor, request):
            raise Http404("Sieć powiązań jest wyłączona dla tego autora.")

        depth = _int_param(request, "depth", 2, 1, 10)
        topn = _int_param(request, "topn", 15, 1, 50)
        rok_od = _int_or_none(request.GET.get("rok_od"))
        rok_do = _int_or_none(request.GET.get("rok_do"))
        uczelnia_zatr = _uczelnia_zatrudnienia(request)
        # filtr tylko-rok (bez źródła/wydawcy) do wyznaczenia zbioru autorów
        filtr_rok = Filtr(rok_od=rok_od, rok_do=rok_do)

        # BFS po sieci + dwa GROUP BY mogą dotknąć do MAKS_WEZLOW_SIECI autorów
        # — twardy statement_timeout ubija patologiczny request (503) zamiast
        # męczyć bazę.
        try:
            with _limit_czasu(STATEMENT_TIMEOUT_FILTR_MS):
                visible_ids = _autorzy_widocznej_sieci(
                    autor.pk, depth, topn, filtr_rok, uczelnia_zatr
                )
                dane = self._zrodla_wydawcy(visible_ids, rok_od, rok_do)
        except OperationalError:
            return JsonResponse(
                {
                    "error": "Zapytanie o źródła sieci trwało za długo — "
                    "zmniejsz głębokość lub liczbę współautorów."
                },
                status=503,
            )

        return JsonResponse(dane)

    @staticmethod
    def _zrodla_wydawcy(autor_ids, rok_od, rok_do):
        """Top-100 źródeł i wydawców (>= MIN_PRAC_ZRODLO prac) wśród prac
        autorów `autor_ids`, z filtrem roku. Zwraca gotowy dict do JSON-a."""
        from django.db.models import Count

        from bpp.models import Autorzy

        base = Autorzy.objects.filter(autor_id__in=autor_ids)
        if rok_od:
            base = base.filter(rekord__rok__gte=rok_od)
        if rok_do:
            base = base.filter(rekord__rok__lte=rok_do)

        zrodla = (
            base.filter(rekord__zrodlo__isnull=False)
            .values("rekord__zrodlo_id", "rekord__zrodlo__nazwa")
            .annotate(n=Count("rekord_id", distinct=True))
            .filter(n__gte=MIN_PRAC_ZRODLO)
            .order_by("-n")[:100]
        )
        wydawcy = (
            base.filter(rekord__wydawca__isnull=False)
            .values("rekord__wydawca_id", "rekord__wydawca__nazwa")
            .annotate(n=Count("rekord_id", distinct=True))
            .filter(n__gte=MIN_PRAC_ZRODLO)
            .order_by("-n")[:100]
        )

        return {
            "zrodla": [
                {
                    "id": z["rekord__zrodlo_id"],
                    "nazwa": z["rekord__zrodlo__nazwa"],
                    "n": z["n"],
                }
                for z in zrodla
            ],
            "wydawcy": [
                {
                    "id": w["rekord__wydawca_id"],
                    "nazwa": w["rekord__wydawca__nazwa"],
                    "n": w["n"],
                }
                for w in wydawcy
            ],
        }
