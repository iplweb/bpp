from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, View

from bpp.models import Autor

from .models import AuthorConnection

# Bezpiecznik payloadu — suwak w UI i tak decyduje, ilu sąsiadów rysujemy.
MAKS_SASIADOW = 500


def _etykieta(autor):
    return f"{autor.imiona} {autor.nazwisko}".strip()


class GrafPowiazanView(TemplateView):
    """Strona z interaktywnym grafem powiązań autora."""

    template_name = "powiazania_autorow/graf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["autor"] = get_object_or_404(Autor, pk=kwargs["pk"])
        return context


class GrafPowiazanDaneView(View):
    """JSON z sąsiadami (współautorami) danego autora.

    Ten sam endpoint obsługuje węzeł centralny i każde rozwinięcie po stronie
    klienta. Sąsiedzi filtrowani do pokazuj=True, sortowani malejąco po liczbie
    wspólnych publikacji.
    """

    def get(self, request, pk):
        autor = get_object_or_404(Autor, pk=pk)
        polaczenia = (
            AuthorConnection.objects.filter(
                Q(primary_author_id=pk) | Q(secondary_author_id=pk)
            )
            .select_related("primary_author", "secondary_author")
            .order_by("-shared_publications_count")
        )

        neighbors = []
        for c in polaczenia:
            # pk z URL-a bywa str — porównujemy z autor.pk (int z bazy).
            inny = (
                c.secondary_author
                if c.primary_author_id == autor.pk
                else c.primary_author
            )
            if not inny.pokazuj:
                continue
            neighbors.append(
                {
                    "id": inny.pk,
                    "label": _etykieta(inny),
                    "url": inny.get_absolute_url(),
                    "shared": c.shared_publications_count,
                }
            )
            if len(neighbors) >= MAKS_SASIADOW:
                break

        return JsonResponse(
            {
                "center": {
                    "id": autor.pk,
                    "label": _etykieta(autor),
                    "url": autor.get_absolute_url(),
                },
                "neighbors": neighbors,
            }
        )
