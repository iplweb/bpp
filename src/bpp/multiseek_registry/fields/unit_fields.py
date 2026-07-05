"""Unit/department-related query objects."""

import logging

from django.db.models import Q
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT,
    DIFFERENT_ALL,
    DIFFERENT_FEMALE,
    EQUAL,
    EQUAL_FEMALE,
    EQUALITY_OPS_ALL,
    AutocompleteQueryObject,
    UnknownOperation,
    ValueListQueryObject,
)

from bpp.models import Autorzy, Jednostka, RodzajJednostki, Uczelnia
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin
from bpp.util import zaloguj_polkniety_wyjatek

from .author_fields import ForeignKeyDescribeMixin
from .constants import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION,
    UNION_FEMALE,
    UNION_OPS_ALL,
)

logger = logging.getLogger(__name__)


class JednostkaQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Jednostka"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
        UNION_FEMALE,
        EQUAL_PLUS_SUB_UNION_FEMALE,
    ]
    model = Jednostka
    search_fields = ["nazwa"]
    field_name = "jednostka"
    url = "bpp:jednostka-widoczna-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka=value)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__jednostka__in=value.get_family())

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(jednostka__in=value.get_family()).values(
                "rekord_id"
            )
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def to_djangoql(self, value, operation):
        """Tlumaczenie na DjangoQL nad Rekord (patrz real_query po semantyke).

        - rownosc -> autorzy.jednostka__rel (picker po jednostce autora)
        - roznosc -> autorzy.jednostka__rel != ...
        - '+ podrzedne' (EQUAL_PLUS_SUB_FEMALE) -> jednostka_z_podjednostkami__rel
          (wirtualne pole MPTT get_family, identyczne z real_query)
        - UNION / '+podrzedne+wspolna' -> None (warning): inny ksztalt zapytania,
          bez gwarancji rownowaznosci bez osobnego pola wirtualnego.
        """
        if type(self) is not JednostkaQueryObject:
            return None  # podklasy (np. AktualnaJednostka...) maja inna semantyke
        op = str(operation)
        try:
            obj = self.value_from_web(value)
        except Exception:  # noqa: BLE001 — uszkodzony/nieistniejacy pk -> nieprzekladalne
            zaloguj_polkniety_wyjatek(
                f"Rozwiązywanie jednostki dla eksportu DjangoQL (value={value!r})",
                logger=logger,
            )
            return None
        if obj is None:
            return None
        label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
        suffix = f'"{label} [{obj.pk}]"'

        union_warning = (
            'Operator „wspólna" przełożono jak równość — w DjangoQL może objąć '
            "innego autora niż pozostałe kryteria."
        )
        if op == str(EQUAL_FEMALE):
            return f"autorzy.jednostka__rel = {suffix}"
        if op == str(DIFFERENT_FEMALE):
            return f"autorzy.jednostka__rel != {suffix}"
        if op == str(EQUAL_PLUS_SUB_FEMALE):
            return f"jednostka_z_podjednostkami__rel = {suffix}"
        if op == str(UNION_FEMALE):
            return f"autorzy.jednostka__rel = {suffix}", union_warning
        if op == str(EQUAL_PLUS_SUB_UNION_FEMALE):
            return f"jednostka_z_podjednostkami__rel = {suffix}", union_warning
        return None


class AktualnaJednostkaAutoraQueryObject(JednostkaQueryObject):
    label = "Aktualna jednostka dowolnego autora"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
    ]
    model = Jednostka
    search_fields = ["nazwa"]
    field_name = "aktualna_jednostka"
    url = "bpp:jednostka-widoczna-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__autor__aktualna_jednostka=value)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__autor__aktualna_jednostka__in=value.get_family())

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(
                autor__aktualna_jednostka__in=value.get_family()
            ).values("rekord_id")
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(autor__aktualna_jednostka=value).values(
                "rekord_id"
            )
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class PierwszaJednostkaQueryObject(JednostkaQueryObject):
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
        UNION_FEMALE,
        EQUAL_PLUS_SUB_UNION_FEMALE,
    ]
    label = "Pierwsza jednostka"
    field_name = "pierwsza_jednostka"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka=value, autorzy__kolejnosc=0)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__jednostka__in=value.get_family(), autorzy__kolejnosc=0)

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(
                jednostka__in=value.get_family(), kolejnosc=0
            ).values("rekord_id")
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka=value, kolejnosc=0).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class WydzialQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    # Faza B (#438): „wydział" = jednostka-korzeń (self-FK, NULL dla top-level).
    # Picker = jednostki top-level; ``real_query`` przez denorm ``wydzial``
    # (poddrzewo) + ``jednostka=value`` (prace samego korzenia). Operatory
    # męskie (EQUAL/DIFFERENT/UNION) zostają. Pole rejestrowane ZAWSZE;
    # widoczność per-uczelnia przez ``option_enabled`` (``uzywaj_wydzialow``).
    label = "Wydział"
    type = AUTOCOMPLETE
    ops = [EQUAL, DIFFERENT, UNION]
    model = Jednostka
    search_fields = ["nazwa"]
    field_name = "wydzial"
    djangoql_field_name = "autorzy__jednostka__wydzial"
    url = "bpp:public-jednostka-toplevel-autocomplete"

    def option_enabled(self, request=None):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is not None:
            return uczelnia.uzywaj_wydzialow
        return True

    def value_from_web(self, value):
        # F4 (#438): „wydział" = jednostka-KORZEŃ (parent IS NULL). Ograniczamy
        # rozwiązywanie wartości do rootów, żeby stary zapisany search z pk
        # nie-roota / dawnego Wydzialu dał GŁOŚNY brak dopasowania (None), a nie
        # cichy zły raport na przypadkowej jednostce o kolidującym pk.
        try:
            value_i = int(value)
        except (TypeError, ValueError):
            return None
        return self.model.objects.filter(parent__isnull=True, pk=value_i).first()

    def to_djangoql(self, value, operation):
        """F5 (#438): eksport DjangoQL tłumaczy TYLKO część poddrzewową
        (``autorzy.jednostka.wydzial__rel``). Union ``| autorzy__jednostka=value``
        (prace przypięte do samego korzenia) nie ma odpowiednika w DjangoQL bez
        osobnego pola wirtualnego, więc emitujemy ostrzeżenie o nierównoważnej
        translacji (precedens: ``JednostkaQueryObject.to_djangoql``)."""
        op = str(operation)
        try:
            obj = self.value_from_web(value)
        except Exception:  # noqa: BLE001 — uszkodzony/nieistniejacy pk -> nieprzekladalne
            zaloguj_polkniety_wyjatek(
                f"Rozwiązywanie wydziału dla eksportu DjangoQL (value={value!r})",
                logger=logger,
            )
            return None
        if obj is None:
            return None
        label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
        suffix = f'"{label} [{obj.pk}]"'
        warning = (
            'Filtr „wydział" przełożono tylko na poddrzewo — eksport DjangoQL '
            "pomija prace przypięte do samej jednostki-korzenia."
        )
        if op == str(EQUAL):
            return f"autorzy.jednostka.wydzial__rel = {suffix}", warning
        if op == str(DIFFERENT):
            return f"autorzy.jednostka.wydzial__rel != {suffix}", warning
        if op == str(UNION):
            return f"autorzy.jednostka.wydzial__rel = {suffix}", warning
        return None

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka__wydzial=value) | Q(autorzy__jednostka=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                Q(jednostka__wydzial=value) | Q(jednostka=value)
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class PierwszyWydzialQueryObject(WydzialQueryObject):
    label = "Pierwszy wydział"
    field_name = "pierwszy_wydzial"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka__wydzial=value, autorzy__kolejnosc=0) | Q(
                autorzy__jednostka=value, autorzy__kolejnosc=0
            )

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                Q(jednostka__wydzial=value) | Q(jednostka=value), kolejnosc=0
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class RodzajJednostkiQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    # Faza B (#438), III-1: CharField ``rodzaj_jednostki`` + TextChoices
    # ``RODZAJ_JEDNOSTKI`` usunięte — filtrujemy przez FK ``rodzaj``
    # (słownik ``RodzajJednostki``, per-tenant edytowalny w adminie).
    # ``field_name`` zostaje ``"rodzaj_jednostki"`` — to etykieta
    # PERSYSTENCJI zapisanych wyszukiwań (identycznie jak przy
    # ``WydzialQueryObject.field_name == "wydzial"`` mimo zmiany semantyki
    # pola), nie nazwa kolumny/lookupu.
    label = "Rodzaj jednostki"
    field_name = "rodzaj_jednostki"

    def _values(self):
        # Lista dynamiczna (property, wzorem ``CharakterFormalnyQueryObject``)
        # — słownik jest edytowalny w adminie, nie da się go zamrozić w
        # czasie importu modułu.
        return list(
            RodzajJednostki.objects.order_by("kolejnosc", "nazwa").values_list(
                "nazwa", flat=True
            )
        )

    values = property(_values)

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        q = Q(**{"autorzy__jednostka__rodzaj__nazwa": value})
        if operation == DIFFERENT:
            return ~q
        return q

    def to_djangoql(self, value, operation):
        op = "!=" if str(operation) == str(DIFFERENT) else "="
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'autorzy.jednostka.rodzaj.nazwa {op} "{escaped}"'
