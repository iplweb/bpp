"""Matchowanie uczelni (PBN Institution)."""

from django.contrib.postgres.search import TrigramSimilarity


def matchuj_uczelnie(nazwa):
    from pbn_api.models import Institution

    try:
        return Institution.objects.get(name=nazwa)
    except Institution.DoesNotExist:
        pass

    res = (
        Institution.objects.annotate(similarity=TrigramSimilarity("name", nazwa))
        .filter(similarity__gte=0.8)
        .order_by("-similarity")
    )

    if res.count() == 1:
        return res.first()
