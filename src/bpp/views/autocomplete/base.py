"""Base mixins and classes for autocomplete views."""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.query_utils import Q


class JednostkaMixin:
    """Mixin for formatting Jednostka results."""

    def get_result_label(self, result):
        if result is not None:
            return str(result)


class NazwaMixin:
    """Mixin for filtering by nazwa field using icontains."""

    def get_queryset(self):
        qs = self.qset
        if self.q:
            self.q = self.q.strip()
            qs = qs.filter(nazwa__icontains=self.q)
        return qs


class NazwaTrigramMixin:
    """Mixin for filtering by nazwa field using trigram similarity."""

    MIN_TRIGRAM_MATCH = 0.05

    def get_queryset(self):
        qs = self.qset
        if self.q:
            self.q = self.q.strip()
            qs = (
                qs.annotate(similarity=TrigramSimilarity("nazwa", self.q))
                .filter(similarity__gte=self.MIN_TRIGRAM_MATCH)
                .order_by("-similarity")[:10]
            )
        return qs


class NazwaLubSkrotMixin:
    """Mixin for filtering by nazwa OR skrot fields using icontains."""

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs


def autocomplete_create_error(msg):
    """Create an error pseudo-object for autocomplete results."""

    class Error:
        pk = -1

        def __str__(self):
            return msg

    return Error()
