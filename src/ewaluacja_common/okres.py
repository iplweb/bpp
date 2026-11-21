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
    {
        "ewaluacja_metryki",
        "ewaluacja_liczba_n",
        "ewaluacja_optymalizacja",
        "ewaluacja_dwudyscyplinowcy",
    }
)


#: Okresy zakładane, gdy tabela okresów jest pusta. Kopia danych z migracji
#: ``0006_okresy_ewaluacji_dane`` (migracja trzyma własną — nie importuje kodu
#: aplikacji).
OKRESY_STARTOWE = (
    (2022, 2025, "Rozporządzenie MNiSW z 22 lutego 2019 r. w sprawie ewaluacji."),
    (
        2026,
        2030,
        "Wg projektu nowelizacji ustawy (2026 r.: okres 5-letni). Do czasu "
        "nowego rozporządzenia punkty i sloty liczone wg zasad 2022–2025.",
    ),
)


def zasiej_okresy_po_migracji(sender, using="default", **kwargs):
    """``post_migrate``: gdy tabela okresów jest PUSTA, zakłada okresy startowe.

    Kod ewaluacji zakłada, że jest choć jeden okres. Migracja danych odpala
    się raz, a ``flush`` (testy transakcyjne, ``manage.py flush``) czyści
    tabelę i woła tylko ``post_migrate`` — stąd ten handler. Niepustej tabeli
    nie rusza, więc okresy poprawione w adminie zostają.
    """
    from django.db import connections

    from ewaluacja_common.models import OkresEwaluacji

    tabela = OkresEwaluacji._meta.db_table
    if tabela not in connections[using].introspection.table_names():
        return  # migracja 0005 jeszcze nie przeszła
    if OkresEwaluacji.objects.using(using).exists():
        return
    OkresEwaluacji.objects.using(using).bulk_create(
        OkresEwaluacji(rok_od=od, rok_do=do, uwagi=uwagi)
        for od, do, uwagi in OKRESY_STARTOWE
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
