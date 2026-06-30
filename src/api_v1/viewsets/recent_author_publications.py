from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from bpp.models import Autor

from .recent_publications_common import (
    odpowiedz_z_publikacjami,
    pobierz_encje_lub_404,
    queryset_rekordow,
)


class RecentAuthorPublicationsViewSet(viewsets.ViewSet):
    """
    ViewSet dla pobierania ostatnich publikacji autora (embed na stronie WWW).

    Zwraca publiczne publikacje autora (z pominięciem statusów ukrytych w
    kontekście API) posortowane wg roku i daty modyfikacji. Identyfikator może
    być numerycznym ID albo slugiem autora. Parametry zapytania: ``limit``,
    ``rok_od``, ``rok_do``.
    """

    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        autor = pobierz_encje_lub_404(Autor, pk, pokazuj=True)
        base = queryset_rekordow().filter(autorzy__autor=autor)
        return odpowiedz_z_publikacjami(
            request,
            base,
            {"autor_id": autor.pk, "autor_nazwa": str(autor)},
        )
