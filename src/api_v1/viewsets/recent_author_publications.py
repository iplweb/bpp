from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from bpp.models import Autor
from bpp.models.cache import Rekord


class RecentAuthorPublicationsViewSet(viewsets.ViewSet):
    """
    ViewSet dla pobierania ostatnich publikacji autora.
    Endpoint zwraca 25 ostatnich publikacji autora posortowanych według daty ostatniej modyfikacji.
    """

    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        """
        Zwraca listę 25 ostatnich publikacji dla konkretnego autora.

        Parameters:
            pk: ID autora

        Returns:
            JSON z danymi autora i listą publikacji
        """
        autor = get_object_or_404(Autor, pk=pk)

        publications = Rekord.objects.filter(autorzy__autor=autor).order_by(
            "-ostatnio_zmieniony"
        )[:25]

        result = []
        for pub in publications:
            # Generowanie URL do publikacji
            if pub.slug:
                pub_url = request.build_absolute_uri(
                    reverse("bpp:browse_praca_by_slug", args=[pub.slug])
                )
            else:
                # Fallback dla rekordów bez slug
                pub_url = request.build_absolute_uri(
                    reverse("bpp:browse_praca", args=[pub.id[0], pub.id[1]])
                )

            result.append(
                {
                    "id": str(pub.id),
                    "opis_bibliograficzny": pub.opis_bibliograficzny_cache,
                    "ostatnio_zmieniony": pub.ostatnio_zmieniony,
                    "url": pub_url,
                }
            )

        resp = Response(
            {
                "autor_id": autor.pk,
                "autor_nazwa": str(autor),
                "count": len(result),
                "publications": result,
            }
        )

        # Allow any origin
        resp["Access-Control-Allow-Origin"] = "*"
        resp["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp["Access-Control-Allow-Headers"] = "Content-Type, Range"
        # Expose headers so JS can read filename/size
        resp["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Length"
        resp["Vary"] = "Origin"
        return resp
