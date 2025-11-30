"""Author-related query objects."""

from django.conf import settings
from django.db.models import Q
from django.db.models.expressions import F
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT,
    DIFFERENT_ALL,
    DIFFERENT_NONE,
    EQUAL,
    EQUAL_NONE,
    EQUALITY_OPS_ALL,
    AutocompleteQueryObject,
    BooleanQueryObject,
    UnknownOperation,
)
from taggit.models import Tag

from bpp import const
from bpp.models import Autor, Autorzy, Dyscyplina_Naukowa, SlowaKluczoweView
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .constants import NULL_VALUE, UNION, UNION_NONE, UNION_OPS_ALL


class ForeignKeyDescribeMixin:
    def value_for_description(self, value):
        if value is None:
            return NULL_VALUE

        return self.value_from_web(value) or "[powiązany obiekt został usunięty]"


class SlowaKluczoweQueryObject(BppMultiseekVisibilityMixin, AutocompleteQueryObject):
    type = AUTOCOMPLETE
    ops = [EQUAL_NONE, DIFFERENT_NONE]
    model = Tag
    search_fields = ["name"]
    url = "bpp:public-taggit-tag-autocomplete"
    label = "Słowa kluczowe"
    field_name = "slowa_kluczowe"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                pk__in=SlowaKluczoweView.objects.filter(tag__name=value).values(
                    "rekord_id"
                )
            )

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class NazwiskoIImieQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Nazwisko i imię"
    type = AUTOCOMPLETE
    ops = [EQUAL_NONE, DIFFERENT_NONE, UNION_NONE]
    model = Autor
    search_fields = ["nazwisko", "imiona"]
    field_name = "autor"
    url = "bpp:public-autor-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__autor=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(autor=value).values("rekord_id")

            ret = Q(pk__in=q)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class NazwiskoIImieWZakresieKolejnosci(NazwiskoIImieQueryObject):
    ops = [EQUAL, UNION_NONE]
    kolejnosc_gte = None
    kolejnosc_lt = None

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                autorzy__autor=value,
                autorzy__kolejnosc__gte=self.kolejnosc_gte,
                autorzy__kolejnosc__lt=self.kolejnosc_lt,
            )

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                autor=value,
                kolejnosc__gte=self.kolejnosc_gte,
                kolejnosc__lt=self.kolejnosc_lt,
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class PierwszeNazwiskoIImie(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 1
    label = "Pierwsze nazwisko i imię"
    field_name = "naz_im_pierwsz"


class OstatnieNazwiskoIImie(NazwiskoIImieWZakresieKolejnosci):
    ops = [
        EQUAL,
    ]
    # bez operatora UNION, bo F('liczba_autorow') nie istnieje, gdy
    # generujemy zapytanie dla niego.
    kolejnosc_gte = F("liczba_autorow") - 1
    kolejnosc_lt = F("liczba_autorow")
    label = "Ostatnie nazwisko i imię"
    public = False
    field_name = "naz_im_ost"


class NazwiskoIImie1do3(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 3
    label = "Nazwisko i imię (od 1 do 3)"
    public = False
    field_name = "naz_im_1_3"


class NazwiskoIImie1do5(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 5
    label = "Nazwisko i imię (od 1 do 5)"
    public = False
    field_name = "naz_im_1_5"


class TypOgolnyAutorQueryObject(NazwiskoIImieQueryObject):
    ops = [EQUAL, DIFFERENT, UNION]

    label = "Autor"
    typ_ogolny = const.TO_AUTOR
    field_name = "typ_og_autor"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                autorzy__autor=value,
                autorzy__typ_odpowiedzialnosci__typ_ogolny=self.typ_ogolny,
            )

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                autor=value, typ_odpowiedzialnosci__typ_ogolny=self.typ_ogolny
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class TypOgolnyRedaktorQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_REDAKTOR
    label = "Redaktor"
    field_name = "typ_og_redaktor"


class TypOgolnyTlumaczQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_TLUMACZ
    label = "Tłumacz"
    field_name = "typ_og_tlumacz"


class TypOgolnyRecenzentQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_RECENZENT
    label = "Recenzent"
    field_name = "typ_og_recenzent"


class DyscyplinaQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Dyscyplina naukowa autora"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_NONE,
    ]
    model = Dyscyplina_Naukowa
    field_name = "nazwa"
    url = "bpp:dyscyplina-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__dyscyplina_naukowa=value)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class OswiadczenieKENQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Oświadczenie KEN"
    ops = [
        EQUAL,
        DIFFERENT,
        UNION,
    ]
    field_name = "oswiadczenie_ken"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__oswiadczenie_ken=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(oswiadczenie_ken=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def enabled(self, request=None):
        if getattr(settings, "BPP_POKAZUJ_OSWIADCZENIE_KEN", False):
            return super().enabled(request)
        return False
