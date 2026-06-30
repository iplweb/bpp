from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from bpp.models import Jednostka

from .recent_publications_common import (
    odpowiedz_z_publikacjami,
    pobierz_encje_lub_404,
    queryset_rekordow,
)


class RecentUnitPublicationsViewSet(viewsets.ViewSet):
    """
    ViewSet dla pobierania ostatnich publikacji jednostki (embed na stronie WWW).

    Zwraca publiczne publikacje jednostki **wraz z jej pod-jednostkami**
    (poddrzewo wydział → katedra → zakład; przez
    :meth:`bpp.models.cache.RekordManager.prace_jednostki`). Identyfikator może
    być numerycznym ID albo slugiem jednostki. Parametry zapytania: ``limit``,
    ``rok_od``, ``rok_do``.
    """

    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        jednostka = pobierz_encje_lub_404(Jednostka, pk, widoczna=True)
        base = queryset_rekordow().prace_jednostki(jednostka)
        return odpowiedz_z_publikacjami(
            request,
            base,
            {"jednostka_id": jednostka.pk, "jednostka_nazwa": str(jednostka)},
        )
