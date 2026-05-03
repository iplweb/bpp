"""Helpery prefetch danych dla listy publikacji w przeglądarce."""

from bpp.models import Autor_Dyscyplina
from bpp.models.cache import Cache_Punktacja_Autora

from ...models import OptimizationPublication


def _build_rekord_ids(ciagle_list, zwarte_list, ct_ciagle, ct_zwarte):
    """Zbuduj słowniki rekord_id dla publikacji."""
    all_rekord_ids = []
    ciagle_rekord_ids = {}
    zwarte_rekord_ids = {}

    for pub in ciagle_list:
        rekord_id = (ct_ciagle.pk, pub.pk)
        ciagle_rekord_ids[pub.pk] = rekord_id
        all_rekord_ids.append(list(rekord_id))

    for pub in zwarte_list:
        rekord_id = (ct_zwarte.pk, pub.pk)
        zwarte_rekord_ids[pub.pk] = rekord_id
        all_rekord_ids.append(list(rekord_id))

    return all_rekord_ids, ciagle_rekord_ids, zwarte_rekord_ids


def _prefetch_selected_publications(all_rekord_ids):
    """Pobierz set rekord_ids wybranych publikacji."""
    selected_rekord_ids = set()
    if all_rekord_ids:
        for op in OptimizationPublication.objects.filter(rekord_id__in=all_rekord_ids):
            selected_rekord_ids.add(tuple(op.rekord_id))
    return selected_rekord_ids


def _prefetch_punktacja_cache(all_rekord_ids):
    """Pobierz cache punktacji dla wszystkich publikacji."""
    punktacja_cache = {}
    if all_rekord_ids:
        for cpa in Cache_Punktacja_Autora.objects.filter(rekord_id__in=all_rekord_ids):
            rekord_key = tuple(cpa.rekord_id)
            if rekord_key not in punktacja_cache:
                punktacja_cache[rekord_key] = {}
            punktacja_cache[rekord_key][(cpa.autor_id, cpa.dyscyplina_id)] = {
                "pkdaut": cpa.pkdaut,
                "slot": cpa.slot,
            }
    return punktacja_cache


def _prefetch_autorzy_by_pub(autorzy_qs, pub_list):
    """Grupuj autorów wg publikacji i zbierz pary (autor_id, rok)."""
    autorzy_by_pub = {}
    autor_rok_pairs = set()
    pub_by_pk = {p.pk: p for p in pub_list}

    for ar in autorzy_qs:
        if ar.rekord_id not in autorzy_by_pub:
            autorzy_by_pub[ar.rekord_id] = []
        autorzy_by_pub[ar.rekord_id].append(ar)
        pub = pub_by_pk.get(ar.rekord_id)
        if pub:
            autor_rok_pairs.add((ar.autor_id, pub.rok))

    return autorzy_by_pub, autor_rok_pairs


def _prefetch_autor_dyscypliny(autor_rok_pairs):
    """Pobierz mapę Autor_Dyscyplina dla par (autor_id, rok)."""
    from django.db.models import Q

    autor_dyscypliny = {}
    if autor_rok_pairs:
        q_filter = Q()
        for autor_id, r in autor_rok_pairs:
            q_filter |= Q(autor_id=autor_id, rok=r)
        for ad in Autor_Dyscyplina.objects.filter(q_filter):
            autor_dyscypliny[(ad.autor_id, ad.rok)] = ad
    return autor_dyscypliny


def _prefetch_autor_max_slots(autor_dysc_pairs):
    """Pobierz maksymalne sloty dla par (autor_id, dyscyplina_id)."""
    from django.db.models import Sum

    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    max_slots = {}
    if not autor_dysc_pairs:
        return max_slots

    autor_ids = {p[0] for p in autor_dysc_pairs}
    dysc_ids = {p[1] for p in autor_dysc_pairs}

    qs = (
        IloscUdzialowDlaAutoraZaCalosc.objects.filter(
            autor_id__in=autor_ids,
            dyscyplina_naukowa_id__in=dysc_ids,
        )
        .values("autor_id", "dyscyplina_naukowa_id")
        .annotate(total=Sum("ilosc_udzialow"))
    )
    for row in qs:
        key = (row["autor_id"], row["dyscyplina_naukowa_id"])
        max_slots[key] = float(row["total"]) if row["total"] else None
    return max_slots


def _prefetch_autor_slot_nazbierany(autor_dysc_pairs):
    """Pobierz nazbierane sloty dla par (autor_id, dyscyplina_id)."""
    from ewaluacja_metryki.models import MetrykaAutora

    nazbierane = {}
    if not autor_dysc_pairs:
        return nazbierane

    autor_ids = {p[0] for p in autor_dysc_pairs}
    dysc_ids = {p[1] for p in autor_dysc_pairs}

    qs = MetrykaAutora.objects.filter(
        autor_id__in=autor_ids,
        dyscyplina_naukowa_id__in=dysc_ids,
    ).values("autor_id", "dyscyplina_naukowa_id", "slot_nazbierany")

    for row in qs:
        key = (row["autor_id"], row["dyscyplina_naukowa_id"])
        val = row["slot_nazbierany"]
        nazbierane[key] = float(val) if val else None
    return nazbierane
