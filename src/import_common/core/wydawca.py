"""Matchowanie wydawców (Wydawca)."""

from django.contrib.postgres.search import TrigramSimilarity

from bpp.models import Wydawca

from ..normalization import normalize_nazwa_wydawcy


def matchuj_wydawce(nazwa, pbn_uid_id=None, similarity=0.9):
    nazwa = normalize_nazwa_wydawcy(nazwa)
    try:
        return Wydawca.objects.get(nazwa=nazwa, alias_dla_id=None)
    except Wydawca.DoesNotExist:
        pass

    if pbn_uid_id is not None:
        try:
            return Wydawca.objects.get(pbn_uid_id=pbn_uid_id)
        except Wydawca.DoesNotExist:
            pass

    loose = (
        Wydawca.objects.annotate(similarity=TrigramSimilarity("nazwa", nazwa))
        .filter(similarity__gte=similarity)
        .order_by("-similarity")[:5]
    )
    if loose.count() > 0 and loose.count() < 2:
        return loose.first()
