"""Buildery list publikacji i autorów dla przeglądarki ewaluacji."""

from bpp.models import (
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)

from .filters import (
    _apply_dyscyplina_nieprzypisana_filter,
    _build_author_filter,
    _build_base_filter,
)
from .prefetch import (
    _build_rekord_ids,
    _prefetch_autor_dyscypliny,
    _prefetch_autor_max_slots,
    _prefetch_autor_slot_nazbierany,
    _prefetch_autorzy_by_pub,
    _prefetch_punktacja_cache,
    _prefetch_selected_publications,
)


def _build_authors_list(
    autor_records,
    rok,
    model_type,
    punktacja_cache,
    autor_dysc,
    autor_max_slots,
    autor_slot_nazbierany,
):
    """Zbuduj listę autorów z prefetchowanych danych."""
    authors = []
    for autor_rekord in autor_records:
        # Sprawdź czy autor ma 2 dyscypliny (używając prefetchowanych danych)
        ad = autor_dysc.get((autor_rekord.autor_id, rok))
        has_two = ad.dwie_dyscypliny() if ad else False

        # Pobierz punktację autora
        key = (autor_rekord.autor_id, autor_rekord.dyscyplina_naukowa_id)
        punktacja = punktacja_cache.get(key, {})

        # Pobierz maksymalny slot i nazbierany slot dla autora w dyscyplinie
        max_slot = autor_max_slots.get(key)
        slot_nazbierany = autor_slot_nazbierany.get(key)

        authors.append(
            {
                "pk": autor_rekord.pk,
                "autor": autor_rekord.autor,
                "dyscyplina": autor_rekord.dyscyplina_naukowa,
                "przypieta": autor_rekord.przypieta,
                "has_two_disciplines": has_two,
                "model_type": model_type,
                "pkdaut": punktacja.get("pkdaut"),
                "slot": punktacja.get("slot"),
                "slot_nazbierany": slot_nazbierany,
                "max_slot": max_slot,
            }
        )

    return authors


def _build_publication_list(
    pub_list,
    model_type,
    rekord_ids,
    selected,
    punktacja_cache,
    autorzy_by_pub,
    ad_map,
    autor_max_slots,
    autor_slot_nazbierany,
):
    """Zbuduj listę publikacji z autorami."""
    publications = []
    for pub in pub_list:
        rekord_id = rekord_ids[pub.pk]
        jest_wybrana = rekord_id in selected
        pub_punktacja = punktacja_cache.get(rekord_id, {})

        authors = _build_authors_list(
            autorzy_by_pub.get(pub.pk, []),
            pub.rok,
            model_type,
            pub_punktacja,
            ad_map,
            autor_max_slots,
            autor_slot_nazbierany,
        )

        if authors:
            publications.append(
                {
                    "pk": pub.pk,
                    "model_type": model_type,
                    "tytul": pub.tytul_oryginalny,
                    "rok": pub.rok,
                    "punkty_kbn": pub.punkty_kbn,
                    "jest_wybrana": jest_wybrana,
                    "url": pub.get_absolute_url(),
                    "authors": authors,
                }
            )
    return publications


def _get_filtered_publications(uczelnia, filters, reported_ids):
    """
    Pobierz publikacje z filtrami.

    Zwraca listę dict z informacjami o publikacjach i autorach.
    Zoptymalizowano pod kątem unikania zapytań N+1.
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    tytul = (filters.get("tytul") or "").strip()

    # Bazowe filtrowanie
    base_filter = _build_base_filter(filters)
    author_filter = _build_author_filter(filters, reported_ids)

    # Pobierz publikacje obu typow
    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(**base_filter)
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(**base_filter)

    if tytul:
        ciagle_qs = ciagle_qs.filter(tytul_oryginalny__icontains=tytul)
        zwarte_qs = zwarte_qs.filter(tytul_oryginalny__icontains=tytul)

    # Ogranicz do publikacji z odpowiednimi autorami
    ciagle_with_authors = Wydawnictwo_Ciagle_Autor.objects.filter(
        **author_filter
    ).values_list("rekord_id", flat=True)
    ciagle_qs = ciagle_qs.filter(pk__in=ciagle_with_authors).distinct()

    zwarte_with_authors = Wydawnictwo_Zwarte_Autor.objects.filter(
        **author_filter
    ).values_list("rekord_id", flat=True)
    zwarte_qs = zwarte_qs.filter(pk__in=zwarte_with_authors).distinct()

    # Filtr po dyscyplinie nieprzypisanej
    ciagle_qs, zwarte_qs = _apply_dyscyplina_nieprzypisana_filter(
        ciagle_qs, zwarte_qs, filters
    )

    # Pobierz content types
    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    # Phase 1: Pobierz wszystkie publikacje jako listy
    ciagle_list = list(ciagle_qs.order_by("rok", "tytul_oryginalny"))
    zwarte_list = list(zwarte_qs.order_by("rok", "tytul_oryginalny"))

    # Phase 2-3: Zbuduj rekord_ids i pobierz wybrane publikacje
    all_rekord_ids, ciagle_rekord_ids, zwarte_rekord_ids = _build_rekord_ids(
        ciagle_list, zwarte_list, ct_ciagle, ct_zwarte
    )
    selected_rekord_ids = _prefetch_selected_publications(all_rekord_ids)
    punktacja_cache = _prefetch_punktacja_cache(all_rekord_ids)

    # Phase 4: Pobierz wszystkich autorów dla publikacji (batch query)
    ciagle_pks = [p.pk for p in ciagle_list]
    zwarte_pks = [p.pk for p in zwarte_list]

    ciagle_autorzy = Wydawnictwo_Ciagle_Autor.objects.filter(
        rekord_id__in=ciagle_pks, **author_filter
    ).select_related("autor", "dyscyplina_naukowa")

    zwarte_autorzy = Wydawnictwo_Zwarte_Autor.objects.filter(
        rekord_id__in=zwarte_pks, **author_filter
    ).select_related("autor", "dyscyplina_naukowa")

    # Grupuj autorów po publikacji
    ciagle_autorzy_by_pub, ciagle_pairs = _prefetch_autorzy_by_pub(
        ciagle_autorzy, ciagle_list
    )
    zwarte_autorzy_by_pub, zwarte_pairs = _prefetch_autorzy_by_pub(
        zwarte_autorzy, zwarte_list
    )

    # Phase 5: Batch pre-fetch Autor_Dyscyplina
    autor_dyscypliny = _prefetch_autor_dyscypliny(ciagle_pairs | zwarte_pairs)

    # Phase 5b: Pobierz maksymalne sloty dla par (autor, dyscyplina)
    autor_dysc_pairs = set()
    for ar in ciagle_autorzy:
        autor_dysc_pairs.add((ar.autor_id, ar.dyscyplina_naukowa_id))
    for ar in zwarte_autorzy:
        autor_dysc_pairs.add((ar.autor_id, ar.dyscyplina_naukowa_id))
    autor_max_slots = _prefetch_autor_max_slots(autor_dysc_pairs)
    autor_slot_nazbierany = _prefetch_autor_slot_nazbierany(autor_dysc_pairs)

    # Phase 6: Zbuduj wyniki
    publications = _build_publication_list(
        ciagle_list,
        "ciagle",
        ciagle_rekord_ids,
        selected_rekord_ids,
        punktacja_cache,
        ciagle_autorzy_by_pub,
        autor_dyscypliny,
        autor_max_slots,
        autor_slot_nazbierany,
    )
    publications.extend(
        _build_publication_list(
            zwarte_list,
            "zwarte",
            zwarte_rekord_ids,
            selected_rekord_ids,
            punktacja_cache,
            zwarte_autorzy_by_pub,
            autor_dyscypliny,
            autor_max_slots,
            autor_slot_nazbierany,
        )
    )

    return publications
