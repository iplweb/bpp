"""Budowniczy meta-cache dla wszystkich autorów BPP.

Pre-loaduje wszystkie metadane autorów potrzebne do fazy ``general``
deduplikatora w stałej liczbie zapytań SQL — niezależnie od N.

Agregaty publikacji liczone są bezpośrednio na tabelach źródłowych
(``Wydawnictwo_Ciagle_Autor``, ``Wydawnictwo_Zwarte_Autor``,
``Patent_Autor``), żeby działać niezależnie od stanu materializowanych
widoków (``bpp_rekord_mat`` / ``bpp_autorzy_mat``) — które w testach
mogą nie być odświeżone po ``baker.make``.
"""

from collections import defaultdict

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Max

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from pbn_api.models import OsobaZInstytucji


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _split_compound(nazwisko: str | None) -> list[str]:
    if not nazwisko:
        return []
    return [_normalize(p) for p in nazwisko.split("-") if p.strip()]


def _aggregate_publications(model, autorzy_meta: dict[int, dict]) -> None:
    """Doliczy do meta agregaty z jednej tabeli ``*_Autor``.

    Wykonuje DOKŁADNIE jedno zapytanie z ``GROUP BY autor_id``.
    """
    rows = (
        model.objects.values("autor_id")
        .annotate(
            cnt=Count("id"),
            max_rok=Max("rekord__rok"),
            lata=ArrayAgg("rekord__rok", distinct=True),
        )
        .filter(autor_id__isnull=False)
    )
    for row in rows:
        pk = row["autor_id"]
        m = autorzy_meta.get(pk)
        if m is None:
            continue
        m["publikacje_count"] += row["cnt"] or 0
        rok_max = row["max_rok"] or 0
        if rok_max > m["max_rok"]:
            m["max_rok"] = rok_max
        for r in row["lata"] or []:
            if r:
                m["lata_publikacji"].add(r)


def build_autor_meta() -> dict[int, dict]:
    """Buduje słownik ``{autor_pk -> meta}`` w stałej liczbie zapytań SQL.

    Zapytania:

    1. ``Autor.objects.only(...)`` — pobranie wszystkich autorów.
    2. Agregat publikacji z ``Wydawnictwo_Ciagle_Autor`` (GROUP BY).
    3. Agregat publikacji z ``Wydawnictwo_Zwarte_Autor`` (GROUP BY).
    4. Agregat publikacji z ``Patent_Autor`` (GROUP BY).
    5. ``Autor_Dyscyplina`` — DISTINCT autor_id.
    6. ``OsobaZInstytucji`` — wszystkie ``personId_id``.

    Łącznie 6 zapytań, niezależnie od liczby autorów.
    """
    autorzy_meta: dict[int, dict] = {}
    # NOTE: include `poprzednie_nazwiska`, `pokazuj_poprzednie_nazwiska`
    # and `pseudonim` because Autor.__str__ reads them — without them
    # `str(autor)` (used by callers such as
    # ``_run_general_phase``) triggers a deferred field load per author
    # (2+ queries per author = O(N) hot-path SQL).
    autor_qs = Autor.objects.only(
        "pk",
        "nazwisko",
        "imiona",
        "orcid",
        "pbn_uid_id",
        "tytul_id",
        "poprzednie_nazwiska",
        "pokazuj_poprzednie_nazwiska",
        "pseudonim",
    )
    for a in autor_qs.iterator():
        autorzy_meta[a.pk] = {
            "obj": a,
            "nazwisko_norm": _normalize(a.nazwisko),
            "nazwisko_parts": _split_compound(a.nazwisko),
            "imiona_norm": [_normalize(i) for i in (a.imiona or "").split() if i],
            "ma_orcid": bool(a.orcid),
            "orcid_value": a.orcid or None,
            "ma_pbn_uid": bool(a.pbn_uid_id),
            "ma_tytul": bool(a.tytul_id),
            "tytul_id": a.tytul_id,
            "ma_osoba_z_instytucji": False,
            "ma_dyscypline": False,
            "publikacje_count": 0,
            "lata_publikacji": set(),
            "max_rok": 0,
        }

    # Agregaty publikacji — po jednym zapytaniu na typ rekordu.
    for model in (
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
        Patent_Autor,
    ):
        _aggregate_publications(model, autorzy_meta)

    # Dyscypliny — jedno DISTINCT.
    for pk in Autor_Dyscyplina.objects.values_list("autor_id", flat=True).distinct():
        m = autorzy_meta.get(pk)
        if m is not None:
            m["ma_dyscypline"] = True

    # OsobaZInstytucji — match po Autor.pbn_uid_id == Scientist.pk
    # (Scientist jest OneToOne z OsobaZInstytucji jako personId).
    osoba_scientist_ids = set(
        OsobaZInstytucji.objects.values_list("personId_id", flat=True)
    )
    for m in autorzy_meta.values():
        pbn_uid_id = m["obj"].pbn_uid_id
        if pbn_uid_id and pbn_uid_id in osoba_scientist_ids:
            m["ma_osoba_z_instytucji"] = True

    return autorzy_meta


def build_buckets(meta: dict[int, dict]) -> dict[str, list[int]]:
    """Buckety ``{nazwisko_norm -> [pk1, pk2, ...]}`` dla pair-generation.

    Autor trafia do bucketu pod swoim znormalizowanym nazwiskiem,
    pod każdym członem nazwiska złożonego (split na ``-``) oraz pod
    odwróconym nazwiskiem złożonym (np. ``Gal-Cisoń`` → ``cisoń-gal``).
    """
    buckets: dict[str, list[int]] = defaultdict(list)
    for pk, m in meta.items():
        nazwisko_norm = m["nazwisko_norm"]
        if not nazwisko_norm:
            continue
        buckets[nazwisko_norm].append(pk)
        parts = m["nazwisko_parts"]
        for part in parts:
            if len(part) > 2 and part != nazwisko_norm:
                buckets[part].append(pk)
        if len(parts) == 2:
            reversed_name = "-".join(reversed(parts))
            if reversed_name != nazwisko_norm:
                buckets[reversed_name].append(pk)
    return dict(buckets)
