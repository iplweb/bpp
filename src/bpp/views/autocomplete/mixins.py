"""
Mixins for autocomplete views.
"""


class SanitizedAutocompleteMixin:
    """
    Mixin to sanitize autocomplete input by truncating excessively long queries.

    This prevents recursion issues and performance problems caused by malicious
    or accidentally pasted long input strings in autocomplete fields.

    Maximum query length is set to 120 characters.
    """

    MAX_QUERY_LENGTH = 120

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to truncate query parameter before processing."""
        # Truncate the query parameter in the request BEFORE parent processes it
        q = request.GET.get("q", "")
        if q and len(q) > self.MAX_QUERY_LENGTH:
            # Create a mutable copy of request.GET
            request.GET = request.GET.copy()
            request.GET["q"] = q[: self.MAX_QUERY_LENGTH]

        return super().dispatch(request, *args, **kwargs)


class UczelniaScopedAutocompleteMixin:
    """Publiczny autocomplete zawężony do uczelni oglądającego (multi-hosted).

    No-op gdy brak uczelni w requeście (brak mapowania Site→Uczelnia) albo gdy
    w systemie jest jedna uczelnia (guard ``tylko_jedna_uczelnia`` z R3a) —
    podpowiedzi i wydajność wtedy identyczne jak dawniej.

    Podklasy ustawiają ``uczelnia_lookups`` — krotkę ścieżek ORM od modelu do
    ``Uczelnia``; są łączone przez OR. ``.distinct()`` zawsze (joiny po historii
    mnożą wiersze; dla FK jest nieszkodliwe).

    UWAGA: umieszczaj ten mixin PRZED konkretnym widokiem w MRO — inaczej
    ``get_queryset`` bazy przesłoni ten i zawężenie po cichu się nie wykona.
    """

    uczelnia_lookups = ("uczelnia",)

    def get_queryset(self):
        qs = super().get_queryset()

        from django.db.models import Q

        from bpp.models import Uczelnia
        from bpp.util.uczelnia_scope import tylko_jedna_uczelnia

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None and not tylko_jedna_uczelnia():
            warunek = Q()
            for lookup in self.uczelnia_lookups:
                warunek |= Q(**{lookup: uczelnia})
            qs = qs.filter(warunek).distinct()
        return qs
