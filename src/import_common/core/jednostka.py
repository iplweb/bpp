"""Matchowanie jednostek (komórki organizacyjne uczelni)."""

from django.db.models import Q

from bpp.models import Jednostka

from ..normalization import normalize_nazwa_jednostki


def wytnij_skrot(jednostka):
    if jednostka.find("(") >= 0 and jednostka.find(")") >= 0:
        jednostka, skrot = jednostka.split("(", 2)
        jednostka = jednostka.strip()
        skrot = skrot[:-1].strip()
        return jednostka, skrot

    return jednostka, None


def _wydzial_filtr(wydzial):
    """``Q`` zawężające jednostki do wydziału podanego NAZWĄ (import legacy).

    Faza B (#438): „wydział" jednostki to zdenormalizowany korzeń
    (``jednostka.wydzial``), a tożsamość dawnego wydziału niesie
    ``root.legacy_wydzial_id``. Dopasowanie po ``wydzial__nazwa`` jest zawodne:
    promowany 1-jednostkowy wydział (0457) ma root == realna jednostka (jej
    własna nazwa ≠ nazwa wydziału), a syntetyczne lustro może mieć suffix
    ``[W<id>]`` na kolizji (F6). Rozwiązujemy więc nazwę → ``Wydzial`` → korzeń
    po ``legacy_wydzial_id``. Fallback na nazwę korzenia, gdy nie ma już wiersza
    ``Wydzial`` o tej nazwie (zachowanie sprzed fixu)."""
    from .tytul_funkcja import matchuj_wydzial

    w = matchuj_wydzial(wydzial)
    if w is not None:
        return Q(wydzial__legacy_wydzial_id=w.id)
    return Q(wydzial__nazwa__iexact=wydzial)


def matchuj_jednostke(nazwa, wydzial=None):
    if nazwa is None:
        return

    nazwa = normalize_nazwa_jednostki(nazwa)
    skrot = nazwa

    if "(" in nazwa and ")" in nazwa:
        nazwa_bez_nawiasow, skrot = wytnij_skrot(nazwa)
        try:
            return Jednostka.objects.get(skrot=skrot)
        except Jednostka.DoesNotExist:
            pass

    try:
        return Jednostka.objects.get(Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa))
    except Jednostka.DoesNotExist:
        if nazwa.endswith("."):
            nazwa = nazwa[:-1].strip()

        try:
            return Jednostka.objects.get(
                Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa)
            )
        except Jednostka.MultipleObjectsReturned as e:
            if wydzial is None:
                raise e

        return Jednostka.objects.get(
            Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa),
            _wydzial_filtr(wydzial),
        )

    except Jednostka.MultipleObjectsReturned as e:
        if wydzial is None:
            raise e

        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa),
            _wydzial_filtr(wydzial),
        )
