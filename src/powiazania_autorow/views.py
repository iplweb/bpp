from collections import defaultdict

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, View

from bpp import const
from bpp.models import Autor

from .models import AuthorConnection

# Bezpiecznik payloadu — suwak w UI i tak decyduje, ilu sąsiadów rysujemy.
MAKS_SASIADOW = 500

# Twardy limit węzłów dla auto-rozwijania sieci (BFS na N poziomów). Chroni
# przed eksplozją depth × rozgałęzienie; po przekroczeniu BFS się zatrzymuje,
# a UI pokazuje informację, że sieć została przycięta.
MAKS_WEZLOW_SIECI = 400

# Backstop dla krawędzi "poprzecznych" (powiązania wewnątrz widocznej grupy).
MAKS_KRAWEDZI_WEWN = 3000


def _etykieta(autor):
    return f"{autor.imiona} {autor.nazwisko}".strip()


def _link_do_pbn(autor, pbn_root):
    """URL do profilu autora w PBN albo "" gdy się nie da go zbudować.

    Root PBN-u pobieramy raz w widoku (jeden Uczelnia.get_default()), żeby nie
    robić N+1 zapytań przez Autor.link_do_pbn() per sąsiad.
    """
    if pbn_root and autor.pbn_uid_id:
        return const.LINK_PBN_DO_AUTORA.format(
            pbn_api_root=pbn_root, pbn_uid_id=autor.pbn_uid_id
        )
    return ""


def _autor_dict(autor, pbn_root, shared=None, metryki=None):
    """Wspólny kształt payloadu dla centrum i każdego sąsiada.

    `metryki` to słownik {works, if_sum, pk_sum} — UI używa wybranej metryki
    jako wielkości kółka (suma prac / IF / PK), przeliczając po stronie klienta
    bez dodatkowego żądania.
    """
    m = metryki or {}
    dane = {
        "id": autor.pk,
        "label": _etykieta(autor),
        "url": autor.get_absolute_url(),
        "tytul": autor.tytul.skrot if autor.tytul_id else "",
        "orcid": autor.orcid or "",
        "pbn_url": _link_do_pbn(autor, pbn_root),
        # metryki autora — sterują wielkością kółka w UI
        "total_works": m.get("works", 0),
        "if_sum": m.get("if_sum", 0.0),
        "pk_sum": m.get("pk_sum", 0.0),
    }
    if shared is not None:
        dane["shared"] = shared
    return dane


def _metryki_prac(autor_ids):
    """Per autor: liczba prac, sumaryczny IF i sumaryczny PK — jednym
    zapytaniem dla całej paczki, z joinu bpp_autorzy_mat → bpp_rekord_mat.
    Zwraca słownik autor_id -> {works, if_sum, pk_sum}; autorzy bez prac
    w cache po prostu nie mają wpisu.
    """
    from django.db.models import Count, Sum

    from bpp.models import Autorzy

    qs = (
        Autorzy.objects.filter(autor_id__in=autor_ids)
        .values("autor_id")
        .annotate(
            works=Count("rekord_id", distinct=True),
            if_sum=Sum("rekord__impact_factor"),
            pk_sum=Sum("rekord__punkty_kbn"),
        )
    )
    return {
        row["autor_id"]: {
            "works": row["works"] or 0,
            "if_sum": float(row["if_sum"] or 0),
            "pk_sum": float(row["pk_sum"] or 0),
        }
        for row in qs
    }


def _pbn_root():
    """Root API PBN-u Uczelni domyślnej (raz na request)."""
    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_default()
    return uczelnia.pbn_api_root if uczelnia is not None else None


def _int_param(request, nazwa, default, lo, hi):
    """Parametr GET jako int przycięty do [lo, hi]; bezpieczny na śmieci."""
    try:
        v = int(request.GET.get(nazwa, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _kandydaci_frontu(front_set):
    """Dla autorów z `front_set` zwraca (kandydaci, inni):

    - kandydaci: id_autora_frontu -> uporządkowana malejąco po `shared` lista
      (id_sąsiada, shared),
    - inni: zbiór wszystkich id sąsiadów (do jednego zapytania o pokazuj).
    """
    conns = (
        AuthorConnection.objects.filter(
            Q(primary_author_id__in=front_set) | Q(secondary_author_id__in=front_set)
        )
        .values("primary_author_id", "secondary_author_id", "shared_publications_count")
        .order_by("-shared_publications_count")
    )
    kandydaci = defaultdict(list)
    inni = set()
    for c in conns:
        p = c["primary_author_id"]
        s = c["secondary_author_id"]
        sh = c["shared_publications_count"]
        if p in front_set:
            kandydaci[p].append((s, sh))
            inni.add(s)
        if s in front_set:
            kandydaci[s].append((p, sh))
            inni.add(p)
    return kandydaci, inni


def _top_widoczni(lista, widoczni, topn):
    """Z uporządkowanej listy (id, shared) bierze top-N widocznych sąsiadów.

    Widoczny sąsiad liczy się do limitu N nawet jeśli już jest w grafie
    (np. rodzic) — odzwierciedla intencję "N współautorów na węzeł".
    """
    wynik = []
    for oid, sh in lista:
        if len(wynik) >= topn:
            break
        if oid in widoczni:
            wynik.append((oid, sh))
    return wynik


def _bfs_siec(centrum_id, depth, topn):
    """BFS po AuthorConnection od centrum do głębokości `depth`.

    Zwraca (level_of, parent_of, krawedzie, przyciecie). `przyciecie` jest
    True, gdy trafiliśmy w MAKS_WEZLOW_SIECI i sieć została obcięta.
    """
    visited = {centrum_id}
    level_of = {centrum_id: 0}
    parent_of = {centrum_id: None}
    krawedzie = []  # [(rodzic_id, dziecko_id, shared), ...]
    frontier = [centrum_id]
    przyciecie = False

    for lvl in range(1, depth + 1):
        if not frontier:
            break
        kandydaci, inni = _kandydaci_frontu(set(frontier))
        widoczni = set(
            Autor.objects.filter(id__in=inni, pokazuj=True).values_list("id", flat=True)
        )
        nowy_front = []
        for fid in frontier:
            for oid, sh in _top_widoczni(kandydaci.get(fid, []), widoczni, topn):
                if oid in visited:
                    continue
                if len(visited) >= MAKS_WEZLOW_SIECI:
                    przyciecie = True
                    break
                visited.add(oid)
                level_of[oid] = lvl
                parent_of[oid] = fid
                krawedzie.append((fid, oid, sh))
                nowy_front.append(oid)
            if przyciecie:
                break
        if przyciecie:
            break
        frontier = nowy_front

    return level_of, parent_of, krawedzie, przyciecie


def _krawedzie_wewnatrz(visited, krawedzie):
    """Wszystkie powiązania między autorami z `visited`, których nie ma w
    drzewie rozwijania (`krawedzie`). To "poprzeczne" linki — np. liść, który
    współpracował też z autorem z wcześniejszego poziomu. Zwraca listę
    {source, target, shared} (przycięta do MAKS_KRAWEDZI_WEWN).
    """
    tree_pairs = {tuple(sorted((a, b))) for a, b, _ in krawedzie}
    wewn = (
        AuthorConnection.objects.filter(
            primary_author_id__in=visited, secondary_author_id__in=visited
        )
        .values("primary_author_id", "secondary_author_id", "shared_publications_count")
        .order_by("-shared_publications_count")
    )
    wynik = []
    for c in wewn:
        a = c["primary_author_id"]
        b = c["secondary_author_id"]
        if a == b:
            continue
        if tuple(sorted((a, b))) in tree_pairs:
            continue
        wynik.append(
            {"source": a, "target": b, "shared": c["shared_publications_count"]}
        )
        if len(wynik) >= MAKS_KRAWEDZI_WEWN:
            break
    return wynik


class GrafPowiazanView(TemplateView):
    """Strona z interaktywnym grafem powiązań autora."""

    template_name = "powiazania_autorow/graf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["autor"] = get_object_or_404(Autor, pk=kwargs["pk"])
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
        pbn_root = _pbn_root()

        polaczenia = (
            AuthorConnection.objects.filter(
                Q(primary_author_id=pk) | Q(secondary_author_id=pk)
            )
            .select_related(
                "primary_author",
                "primary_author__tytul",
                "secondary_author",
                "secondary_author__tytul",
            )
            .order_by("-shared_publications_count")
        )

        wybrani = []  # [(Autor, shared_count), ...] po filtrze pokazuj
        for c in polaczenia:
            # pk z URL-a bywa str — porównujemy z autor.pk (int z bazy).
            inny = (
                c.secondary_author
                if c.primary_author_id == autor.pk
                else c.primary_author
            )
            if not inny.pokazuj:
                continue
            wybrani.append((inny, c.shared_publications_count))
            if len(wybrani) >= MAKS_SASIADOW:
                break

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
        depth = _int_param(request, "depth", 2, 1, 10)
        topn = _int_param(request, "topn", 15, 1, 50)

        level_of, parent_of, krawedzie, przyciecie = _bfs_siec(autor.pk, depth, topn)
        visited = set(level_of.keys())

        autorzy = {
            a.pk: a
            for a in Autor.objects.filter(id__in=visited).select_related("tytul")
        }
        pbn_root = _pbn_root()
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
        # Krawędzie "poprzeczne": wszystkie powiązania MIĘDZY widocznymi
        # autorami, których nie ma w drzewie rozwijania. UI pokazuje je na
        # żądanie (przełącznik), żeby zobaczyć powiązania wewnątrz grupy bez
        # klikania każdego autora.
        extra_edges = _krawedzie_wewnatrz(visited, krawedzie)

        return JsonResponse(
            {
                "center_id": autor.pk,
                "nodes": nodes,
                "edges": edges,
                "extra_edges": extra_edges,
                "truncated": przyciecie,
            }
        )
