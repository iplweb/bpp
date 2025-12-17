"""Publication type and format query objects."""

from django.db.models import Q
from mptt.forms import TreeNodeChoiceFieldMixin
from mptt.settings import DEFAULT_LEVEL_INDICATOR
from multiseek.logic import (
    DIFFERENT,
    DIFFERENT_ALL,
    EQUAL,
    EQUALITY_OPS_ALL,
    VALUE_LIST,
    QueryObject,
    UnknownOperation,
    ValueListQueryObject,
)

from bpp import const
from bpp.models import Autorzy, Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.konferencja import Konferencja
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .constants import UNION, UNION_OPS_ALL


class Typ_OdpowiedzialnosciQueryObject(BppMultiseekVisibilityMixin, QueryObject):
    label = "Typ odpowiedzialności"
    type = VALUE_LIST
    values = Typ_Odpowiedzialnosci.objects.all()
    ops = [EQUAL, DIFFERENT, UNION]
    field_name = "typ_odpowiedzialnosci"
    public = False

    def value_from_web(self, value):
        return Typ_Odpowiedzialnosci.objects.filter(nazwa=value).first()

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__typ_odpowiedzialnosci=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(typ_odpowiedzialnosci=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class TypRekorduObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Typ rekordu"
    field_name = "typ_rekordu"
    values = ["publikacje", "streszczenia", "inne"]
    ops = [EQUAL, DIFFERENT]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "publikacje":
            charaktery = Charakter_Formalny.objects.filter(publikacja=True)
        elif value == "streszczenia":
            charaktery = Charakter_Formalny.objects.filter(streszczenie=True)
        else:
            charaktery = (
                Charakter_Formalny.objects.all()
                .exclude(streszczenie=True)
                .exclude(publikacja=True)
            )

        q = Q(**{"charakter_formalny__in": charaktery})
        if operation == DIFFERENT:
            return ~q
        return q


class CharakterOgolnyQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Charakter formalny ogólny"
    field_name = "charakter_formalny_ogolny"
    values = ["artykuł", "rozdział", "książka", "inne"]
    ops = [EQUAL, DIFFERENT]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "artykuł":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_ARTYKUL
            )
        elif value == "rozdział":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_ROZDZIAL
            )
        elif value == "książka":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_KSIAZKA
            )
        elif value == "inne":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_INNE
            )
        else:
            raise NotImplementedError()

        q = Q(**{"charakter_formalny__in": charaktery})
        if operation == DIFFERENT:
            return ~q
        return q


class CharakterFormalnyQueryObject(
    BppMultiseekVisibilityMixin, TreeNodeChoiceFieldMixin, ValueListQueryObject
):
    field_name = "charakter_formalny"
    label = "Charakter formalny"

    start_level = 0

    def _values(self):
        for elem in self.queryset:
            yield self.label_from_instance(elem)

    values = property(_values)

    def value_from_web(self, value):
        if value is None:
            return None
        return Charakter_Formalny.objects.filter(
            nazwa=value.lstrip("-").lstrip(" ")
        ).first()

    def __init__(self, *args, **kwargs):
        ValueListQueryObject.__init__(self, *args, **kwargs)

        self.level_indicator = kwargs.pop("level_indicator", DEFAULT_LEVEL_INDICATOR)

    @property
    def queryset(self):
        queryset = Charakter_Formalny.objects.all()
        # if a queryset is supplied, enforce ordering
        if hasattr(queryset, "model"):
            mptt_opts = queryset.model._mptt_meta
            queryset = queryset.order_by(mptt_opts.tree_id_attr, mptt_opts.left_attr)
        return queryset
        # self.queryset = queryset

    def real_query(self, value, operation, validate_operation=True):
        ret = None

        if operation in [str(x) for x in EQUALITY_OPS_ALL]:
            ret = Q(
                **{self.field_name + "__in": value.get_descendants(include_self=True)}
            )

        else:
            if validate_operation:
                raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class RodzajKonferenckjiQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Rodzaj konferencji"
    field_name = "rodzaj_konferencji"
    values = ["krajowa", "międzynarodowa", "lokalna"]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "krajowa":
            tk = Konferencja.TK_KRAJOWA
        elif value == "międzynarodowa":
            tk = Konferencja.TK_MIEDZYNARODOWA
        else:
            tk = Konferencja.TK_LOKALNA

        q = Q(**{"konferencja__typ_konferencji": tk})
        if operation == DIFFERENT:
            return ~q
        return q
