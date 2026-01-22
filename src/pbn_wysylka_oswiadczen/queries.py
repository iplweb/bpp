"""Shared query functions for pbn_wysylka_oswiadczen module."""

from django.db.models import Count, Q

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


def get_publications_queryset(
    rok_od=2022, rok_do=2025, tytul=None, tylko_odpiete=False, with_annotations=False
):
    """
    Get publications that need statements sent to PBN.

    Criteria:
    - rok in range [rok_od, rok_do]
    - has pbn_uid_id (synced with PBN)
    - (optional) title contains search text (case-insensitive)
    - (optional) tylko_odpiete: only publications with all declarations unattached
      (liczba_oswiadczen > 0 AND liczba_przypietych == 0)

    Args:
        rok_od: Start year (inclusive)
        rok_do: End year (inclusive)
        tytul: Optional title filter (case-insensitive)
        tylko_odpiete: If True, only return publications with unattached declarations
        with_annotations: If True, add liczba_oswiadczen and liczba_przypietych
            annotations (needed for display in views)

    Returns:
        tuple: (ciagle_queryset, zwarte_queryset)

    Note: Simplified criteria (without author discipline/employment requirements)
    allow cleanup of incorrectly sent statements when author discipline is removed.
    """
    base_filter = {
        "rok__gte": rok_od,
        "rok__lte": rok_do,
        "pbn_uid_id__isnull": False,
    }

    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(**base_filter).select_related(
        "pbn_uid"
    )
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(**base_filter).select_related(
        "pbn_uid"
    )

    # Add annotations if needed (for views displaying counts)
    if with_annotations:
        annotations = {
            "liczba_oswiadczen": Count(
                "autorzy_set__pk",
                filter=Q(autorzy_set__dyscyplina_naukowa__isnull=False),
                distinct=True,
            ),
            "liczba_przypietych": Count(
                "autorzy_set__pk",
                filter=Q(
                    autorzy_set__przypieta=True,
                    autorzy_set__dyscyplina_naukowa__isnull=False,
                ),
                distinct=True,
            ),
        }
        ciagle_qs = ciagle_qs.annotate(**annotations)
        zwarte_qs = zwarte_qs.annotate(**annotations)

    # Apply title filter if provided
    if tytul:
        ciagle_qs = ciagle_qs.filter(tytul_oryginalny__icontains=tytul)
        zwarte_qs = zwarte_qs.filter(tytul_oryginalny__icontains=tytul)

    # Apply tylko_odpiete filter (publications with all declarations unattached)
    # Requires annotations to be present
    if tylko_odpiete:
        if not with_annotations:
            raise ValueError("tylko_odpiete=True requires with_annotations=True")
        ciagle_qs = ciagle_qs.filter(liczba_oswiadczen__gt=0, liczba_przypietych=0)
        zwarte_qs = zwarte_qs.filter(liczba_oswiadczen__gt=0, liczba_przypietych=0)

    return ciagle_qs.distinct(), zwarte_qs.distinct()
