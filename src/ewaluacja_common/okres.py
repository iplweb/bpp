"""Wybór okresu ewaluacji: ostatnio wybrany przez użytkownika na pasku okresu
(pod ścieżką nawigacji) stron ewaluacji (sesja + trwale
``WybranyOkresEwaluacji``), a bez wyboru — domyślny wg bieżącego roku.

Użycie w widokach: ``okres = okres_dla_request(request)``, potem
``okres.rok_od`` / ``okres.rok_do`` / ``okres.lata``.
"""

from django.utils import timezone

KLUCZ_SESJI = "okres_ewaluacji_pk"

#: Strony, na których pod ścieżką nawigacji pokazujemy pasek wyboru okresu
#: (i które liczą dane dla wybranego okresu): przestrzeń nazw URL (cała
#: aplikacja) albo ``przestrzeń:nazwa`` (pojedynczy widok).
APLIKACJE_Z_OKRESEM = frozenset(
    {
        "ewaluacja_metryki",
        "ewaluacja_liczba_n",
        "ewaluacja_optymalizacja",
        "ewaluacja_dwudyscyplinowcy",
        "snapshot_odpiec",
        "oswiadczenia:wydruk",
        "pbn_wysylka_oswiadczen",
        "komparator_pbn",
        "pbn_komparator_zrodel",
        "komparator_pbn_udzialy:list",
        "komparator_publikacji_pbn:comparison_list",
        "deduplikator_autorow",
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
    nie rusza (okresy zmieniamy migracjami danych, nie tutaj).
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


def _zapamietany_dla_uzytkownika(request):
    """Ostatni okres wybrany przez zalogowanego użytkownika (z poprzednich
    sesji) albo ``None``."""
    from ewaluacja_common.models import WybranyOkresEwaluacji

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    wybor = (
        WybranyOkresEwaluacji.objects.filter(user=user).select_related("okres").first()
    )
    return wybor.okres if wybor is not None else None


def pokazac_pasek_okresu(resolver_match):
    """Czy strona (wg ``request.resolver_match``) ma pasek wyboru okresu."""
    if resolver_match is None:
        return False
    przestrzen = resolver_match.namespace.split(":")[0]
    return (
        przestrzen in APLIKACJE_Z_OKRESEM
        or f"{przestrzen}:{resolver_match.url_name}" in APLIKACJE_Z_OKRESEM
    )


def okres_dla_request(request):
    """Okres wybrany w sesji (jeśli nadal istnieje), potem ostatnio wybrany
    przez użytkownika (trwale), na końcu domyślny. Wynik zapamiętany na
    obiekcie ``request`` (jedno zapytanie na żądanie)."""
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
        okres = _zapamietany_dla_uzytkownika(request)
        if okres is not None and hasattr(request, "session"):
            request.session[KLUCZ_SESJI] = okres.pk
    if okres is None:
        okres = okres_domyslny()
    request._okres_ewaluacji = okres
    return okres


def lata_okresu(request):
    """``(rok_od, rok_do)`` okresu ewaluacji wybranego na pasku okresu (albo
    w adresie URL); bez wyboru — okresu domyślnego. Wspólne źródło domyślnego
    zakresu lat komparatorów PBN. Gdy tabela okresów jest pusta (awaryjnie)
    — lata ostatniego z ``OKRESY_STARTOWE``."""
    okres = okres_dla_request(request)
    if okres is None:
        return OKRESY_STARTOWE[-1][:2]
    return okres.rok_od, okres.rok_do


def ustaw_okres(request, okres):
    """Zapamiętaj wybór w sesji i — dla zalogowanego — na stałe."""
    from ewaluacja_common.models import WybranyOkresEwaluacji

    request.session[KLUCZ_SESJI] = okres.pk
    request._okres_ewaluacji = okres
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        WybranyOkresEwaluacji.objects.update_or_create(
            user=user, defaults={"okres": okres}
        )
