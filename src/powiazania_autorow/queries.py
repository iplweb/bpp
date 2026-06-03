from collections import defaultdict
from contextlib import contextmanager

from django.db import connection, transaction
from django.db.models import Q

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

# Źródła/wydawcy z mniejszą liczbą prac nie trafiają do comboboxu (szum).
MIN_PRAC_ZRODLO = 4

# Przy aktywnym filtrze (rok/źródło/wydawca) liczymy współautorstwa z cache
# (self-join na bpp_autorzy_mat) zamiast z gotowego AuthorConnection — tańszego
# precomputed odpowiednika nie ma. Batch per poziom jest tani, ale głębokość
# tniemy dodatkowo, żeby self-join nie rozjechał się przy gęstych sieciach.
MAKS_GLEBOKOSC_FILTR = 4

# Twardy limit czasu (ms) dla zapytań liczonych z cache przy aktywnym filtrze.
# Patologiczny self-join `rekord__autorzy` na gęstej sieci ma ubić własny
# request (timeout → 503), zamiast męczyć bazę aż do timeoutu connection-poola.
STATEMENT_TIMEOUT_FILTR_MS = 8000

# Maks. liczba id źródeł/wydawców branych z requestu — ochrona przed
# gigantycznym `IN (...)` podsuniętym ręcznie spreparowanym requestem.
MAKS_ZRODEL_WYDAWCOW = 100


@contextmanager
def _limit_czasu(ms):
    """Ogranicza czas pojedynczego zapytania do `ms` przez `SET LOCAL
    statement_timeout`. `SET LOCAL` żyje tylko w obrębie transakcji, więc
    całość owijamy w `transaction.atomic()` — po wyjściu limit znika.
    Przekroczenie → `OperationalError` (łapane wyżej, zwracamy 503).
    """
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL statement_timeout = %s", [ms])
        yield


class Filtr:
    """Filtr prac po roku (od-do) oraz po WIELU źródłach/wydawcach (oba
    indeksowane FK w bpp_rekord_mat). Źródła i wydawcy łączymy OR-em (praca z
    któregokolwiek zaznaczonego), rok to AND. `aktywny()` decyduje, czy w ogóle
    schodzimy ze ścieżki AuthorConnection na liczenie z cache.
    """

    def __init__(self, rok_od=None, rok_do=None, zrodla=None, wydawcy=None):
        self.rok_od = rok_od
        self.rok_do = rok_do
        self.zrodla = zrodla or []
        self.wydawcy = wydawcy or []

    def aktywny(self):
        return bool(self.rok_od or self.rok_do or self.zrodla or self.wydawcy)

    def zastosuj(self, qs):
        """Nakłada WHERE-y na queryset po `Autorzy` (przez relację rekord)."""
        if self.rok_od:
            qs = qs.filter(rekord__rok__gte=self.rok_od)
        if self.rok_do:
            qs = qs.filter(rekord__rok__lte=self.rok_do)
        if self.zrodla or self.wydawcy:
            src = Q()
            if self.zrodla:
                src |= Q(rekord__zrodlo_id__in=self.zrodla)
            if self.wydawcy:
                src |= Q(rekord__wydawca_id__in=self.wydawcy)
            qs = qs.filter(src)
        return qs


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _ints(values):
    """Lista intów z listy stringów (pomija śmieci)."""
    out = []
    for v in values:
        iv = _int_or_none(v)
        if iv is not None:
            out.append(iv)
    return out


def _filtr_z_request(request):
    return Filtr(
        rok_od=_int_or_none(request.GET.get("rok_od")),
        rok_do=_int_or_none(request.GET.get("rok_do")),
        # cap listy id, żeby nie zbudować gigantycznego `IN (...)`
        zrodla=_ints(request.GET.getlist("zrodlo"))[:MAKS_ZRODEL_WYDAWCOW],
        wydawcy=_ints(request.GET.getlist("wydawca"))[:MAKS_ZRODEL_WYDAWCOW],
    )


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


def _kandydaci_cache(front_set, filtr):
    """Odpowiednik `_kandydaci_frontu`, ale liczony z materializowanego cache
    z filtrem rok/źródło/wydawca. JEDNO zapytanie na poziom: self-join po
    `rekord__autorzy` (a1 = autor frontu, a2 = współautor na tej samej pracy),
    `Count(DISTINCT rekord)` = liczba wspólnych prac. `rekord_id` to klucz
    krotkowy (TupleField), więc liczymy przez relację, nie przez listę id.
    """
    from django.db.models import Count, F

    from bpp.models import Autorzy

    rows = (
        filtr.zastosuj(Autorzy.objects.filter(autor_id__in=front_set))
        .values("autor_id", co=F("rekord__autorzy__autor_id"))
        .annotate(shared=Count("rekord_id", distinct=True))
    )

    wspolne = defaultdict(dict)  # frontier_id -> {co_id: shared}
    for r in rows:
        fa = r["autor_id"]
        co = r["co"]
        if co is None or co == fa:
            continue
        wspolne[fa][co] = r["shared"]

    kandydaci = {}
    inni = set()
    for fa, d in wspolne.items():
        kandydaci[fa] = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
        inni.update(d.keys())
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


def _bfs_siec(centrum_id, depth, topn, filtr=None):
    """BFS od centrum do głębokości `depth`.

    Bez filtra czerpie z gotowego AuthorConnection; z filtrem (rok/źródło/
    wydawca) liczy współautorstwa z cache. Zwraca (level_of, parent_of,
    krawedzie, przyciecie); `przyciecie` = trafienie w MAKS_WEZLOW_SIECI.
    """
    z_filtrem = filtr is not None and filtr.aktywny()
    visited = {centrum_id}
    level_of = {centrum_id: 0}
    parent_of = {centrum_id: None}
    krawedzie = []  # [(rodzic_id, dziecko_id, shared), ...]
    frontier = [centrum_id]
    przyciecie = False

    for lvl in range(1, depth + 1):
        if not frontier:
            break
        if z_filtrem:
            kandydaci, inni = _kandydaci_cache(set(frontier), filtr)
        else:
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


def _pary_wewnatrz_cache(visited, filtr):
    """Pary (a, b) -> liczba wspólnych prac MIĘDZY autorami z `visited`, liczone
    z cache po filtrze (jeden self-join `rekord__autorzy`, oba końce w
    `visited`). Dla widoku z filtrem — AuthorConnection nie zna roku/źródła."""
    from django.db.models import Count, F

    from bpp.models import Autorzy

    rows = (
        filtr.zastosuj(Autorzy.objects.filter(autor_id__in=visited))
        .filter(rekord__autorzy__autor_id__in=visited)
        .values("autor_id", co=F("rekord__autorzy__autor_id"))
        .annotate(shared=Count("rekord_id", distinct=True))
    )
    pary = {}
    for r in rows:
        a = r["autor_id"]
        b = r["co"]
        if b is None or a == b:
            continue
        # każda nieskierowana para pada dwa razy (a→b i b→a) z tym samym shared
        klucz = (a, b) if a < b else (b, a)
        pary[klucz] = r["shared"]
    return pary


def _krawedzie_wewnatrz(visited, krawedzie, filtr=None):
    """Wszystkie powiązania między autorami z `visited`, których nie ma w
    drzewie rozwijania (`krawedzie`). To "poprzeczne" linki — np. liść, który
    współpracował też z autorem z wcześniejszego poziomu. Zwraca listę
    {source, target, shared} (przycięta do MAKS_KRAWEDZI_WEWN).
    """
    tree_pairs = {tuple(sorted((a, b))) for a, b, _ in krawedzie}
    wynik = []

    if filtr is not None and filtr.aktywny():
        pary = _pary_wewnatrz_cache(visited, filtr)
        for (a, b), sh in sorted(pary.items(), key=lambda kv: -kv[1]):
            if (a, b) in tree_pairs:
                continue
            wynik.append({"source": a, "target": b, "shared": sh})
            if len(wynik) >= MAKS_KRAWEDZI_WEWN:
                break
        return wynik

    wewn = (
        AuthorConnection.objects.filter(
            primary_author_id__in=visited, secondary_author_id__in=visited
        )
        .values("primary_author_id", "secondary_author_id", "shared_publications_count")
        .order_by("-shared_publications_count")
    )
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


def _sasiedzi_authorconnection(autor):
    """Sąsiedzi centrum z gotowego AuthorConnection (ścieżka bez filtra)."""
    polaczenia = (
        AuthorConnection.objects.filter(
            Q(primary_author_id=autor.pk) | Q(secondary_author_id=autor.pk)
        )
        .select_related(
            "primary_author",
            "primary_author__tytul",
            "secondary_author",
            "secondary_author__tytul",
        )
        .order_by("-shared_publications_count")
    )
    wybrani = []
    for c in polaczenia:
        inny = (
            c.secondary_author if c.primary_author_id == autor.pk else c.primary_author
        )
        if not inny.pokazuj:
            continue
        wybrani.append((inny, c.shared_publications_count))
        if len(wybrani) >= MAKS_SASIADOW:
            break
    return wybrani


def _sasiedzi_cache(autor, filtr):
    """Sąsiedzi centrum policzeni z cache po filtrze (rok/źródło/wydawca)."""
    kandydaci, _ = _kandydaci_cache({autor.pk}, filtr)
    pary = kandydaci.get(autor.pk, [])  # [(co_id, shared)] malejąco
    co_ids = [a for a, _ in pary]
    widoczne = set(
        Autor.objects.filter(id__in=co_ids, pokazuj=True).values_list("id", flat=True)
    )
    pary = [(a, s) for a, s in pary if a in widoczne][:MAKS_SASIADOW]
    autorzy = {
        a.pk: a
        for a in Autor.objects.filter(id__in=[a for a, _ in pary]).select_related(
            "tytul"
        )
    }
    return [(autorzy[a], s) for a, s in pary if a in autorzy]


def _zakres_lat(autor_id):
    """(min, max) rok prac autora — do ustawienia granic suwaka lat w UI."""
    from django.db.models import Max, Min

    from bpp.models import Autorzy

    agg = Autorzy.objects.filter(autor_id=autor_id).aggregate(
        mn=Min("rekord__rok"), mx=Max("rekord__rok")
    )
    return agg["mn"], agg["mx"]
