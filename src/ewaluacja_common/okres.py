"""Wybór okresu ewaluacji: domyślny (wg bieżącego roku) albo wybrany przez
użytkownika w górnej belce stron ewaluacji (pamiętany w sesji).

Użycie w widokach: ``okres = okres_dla_request(request)``, potem
``okres.rok_od`` / ``okres.rok_do`` / ``okres.lata``.
"""

from django.utils import timezone

KLUCZ_SESJI = "okres_ewaluacji_pk"

#: Przestrzenie nazw URL stron, na których w górnej belce pokazujemy wybór
#: okresu (i które liczą dane dla wybranego okresu).
APLIKACJE_Z_OKRESEM = frozenset(
    {"ewaluacja_metryki", "ewaluacja_liczba_n", "ewaluacja_optymalizacja"}
)


def okres_domyslny(rok=None):
    """Okres zawierający ``rok`` (domyślnie bieżący). Gdy żaden go nie
    zawiera — ostatni okres, który już się zaczął; a gdy i takiego nie ma —
    pierwszy z listy. ``None``, gdy tabela okresów jest pusta."""
    from ewaluacja_common.models import OkresEwaluacji

    if rok is None:
        rok = timezone.localdate().year
    okresy = list(OkresEwaluacji.objects.all())
    for okres in okresy:
        if okres.zawiera(rok):
            return okres
    rozpoczete = [o for o in okresy if o.rok_od <= rok]
    if rozpoczete:
        return rozpoczete[-1]
    return okresy[0] if okresy else None


def okres_dla_request(request):
    """Okres wybrany w sesji (jeśli nadal istnieje) albo domyślny.
    Wynik zapamiętany na obiekcie ``request`` (jedno zapytanie na żądanie)."""
    from ewaluacja_common.models import OkresEwaluacji

    if request is None:
        return okres_domyslny()
    if hasattr(request, "_okres_ewaluacji"):
        return request._okres_ewaluacji

    okres = None
    pk = getattr(request, "session", {}).get(KLUCZ_SESJI)
    if pk is not None:
        okres = OkresEwaluacji.objects.filter(pk=pk).first()
    if okres is None:
        okres = okres_domyslny()
    request._okres_ewaluacji = okres
    return okres


def ustaw_okres(request, okres):
    request.session[KLUCZ_SESJI] = okres.pk
    request._okres_ewaluacji = okres
