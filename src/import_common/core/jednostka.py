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
    """``Q`` zawężające jednostki do dawnego wydziału podanego NAZWĄ.

    Faza C (#438): „wydział" = jednostka top-level. ``matchuj_wydzial`` zwraca
    root-Jednostkę (po nazwie lub ``poprzednie_nazwy``); zawężamy do jednostek
    POD nim (denorm ``wydzial`` → root) ORAZ do SAMEGO roota (który ma denorm
    ``wydzial=None``, więc pierwsza gałąź by go wykluczyła). Fallback na nazwę
    korzenia, gdy żaden root nie pasuje."""
    from .tytul_funkcja import matchuj_wydzial

    root = matchuj_wydzial(wydzial)
    if root is not None:
        return Q(wydzial=root) | Q(pk=root.pk)
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
