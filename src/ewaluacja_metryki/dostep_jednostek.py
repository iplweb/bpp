"""Kto widzi „Metryki jednostek” (FD#617) i których jednostek.

- pełne uprawnienia ewaluacji (superuser, grupa „wprowadzanie danych”)
  → wszystkie jednostki,
- jednostki wskazane w profilu użytkownika (``BppUser.jednostki_metryk``,
  ustawia administrator) → te jednostki razem z podjednostkami,
- konto powiązane z autorem, który JEST TERAZ kierownikiem jednostki
  (funkcja „kierownik” w ``Autor_Jednostka``, w datach zatrudnienia)
  → ta jednostka razem z podjednostkami.

Zestawienie zawiera imienne oceny pracowników, więc każdy widok musi
sprawdzać dostęp do KONKRETNEJ jednostki, a nie tylko „czy w ogóle”.
"""

from django.db.models import Q
from django.utils import timezone

from bpp.models import Jednostka
from bpp.permissions import moze_wprowadzac_dane

FUNKCJA_KIEROWNIKA = "kierownik"


def jednostki_kierowane(user):
    """Jednostki, których kierownikiem jest dziś autor powiązany z kontem."""
    if getattr(user, "autor_id", None) is None:
        return Jednostka.objects.none()
    dzis = timezone.now().date()
    # Warunki w JEDNYM filter() — muszą dotyczyć tego samego przypisania
    # (jak w ``Jednostka.kierownik``).
    return Jednostka.objects.filter(
        Q(autor_jednostka__zakonczyl_prace__gte=dzis)
        | Q(autor_jednostka__zakonczyl_prace=None),
        Q(autor_jednostka__rozpoczal_prace__lte=dzis)
        | Q(autor_jednostka__rozpoczal_prace=None),
        autor_jednostka__autor_id=user.autor_id,
        autor_jednostka__funkcja__nazwa=FUNKCJA_KIEROWNIKA,
    ).distinct()


def widzi_wszystkie_jednostki(user) -> bool:
    return moze_wprowadzac_dane(user)


def jednostki_do_wgladu(user):
    """Queryset jednostek, których metryki ``user`` może oglądać, albo
    ``None``, gdy widzi wszystkie (pełne uprawnienia ewaluacji)."""
    if not user.is_authenticated:
        return Jednostka.objects.none()
    if widzi_wszystkie_jednostki(user):
        return None

    bazowe_pk = set(user.jednostki_metryk.values_list("pk", flat=True))
    bazowe_pk |= set(jednostki_kierowane(user).values_list("pk", flat=True))
    if not bazowe_pk:
        return Jednostka.objects.none()
    # Jednostki razem z poddrzewami MPTT. Ręcznie z pól drzewa, bo
    # ``get_queryset_descendants`` robi ``.only()``, które gryzie się
    # z domyślnym ``select_related`` menedżera jednostek.
    poddrzewa = Q(pk__in=bazowe_pk)
    for tree_id, lft, rght in Jednostka.objects.filter(pk__in=bazowe_pk).values_list(
        "tree_id", "lft", "rght"
    ):
        poddrzewa |= Q(tree_id=tree_id, lft__gte=lft, rght__lte=rght)
    return Jednostka.objects.filter(poddrzewa)


def moze_ogladac_metryki_jednostki(user, jednostka) -> bool:
    dozwolone = jednostki_do_wgladu(user)
    if dozwolone is None:
        return user.is_authenticated
    return dozwolone.filter(pk=jednostka.pk).exists()


def ma_dostep_do_metryk_jednostek(user) -> bool:
    """Czy pokazać użytkownikowi „Metryki jednostek” w ogóle."""
    dozwolone = jednostki_do_wgladu(user)
    return dozwolone is None or dozwolone.exists()
