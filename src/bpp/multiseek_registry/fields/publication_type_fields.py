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
    djangoql_field_name = "autorzy__typ_odpowiedzialnosci"
    djangoql_value_field = "nazwa"
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

    def to_djangoql(self, value, operation):
        neg = str(operation) in {str(o) for o in DIFFERENT_ALL}
        if value == "publikacje":
            frag = "charakter_formalny.publikacja = True"
        elif value == "streszczenia":
            frag = "charakter_formalny.streszczenie = True"
        elif value == "inne":
            frag = (
                "(charakter_formalny.publikacja = False "
                "and charakter_formalny.streszczenie = False)"
            )
        else:
            return None
        if neg:
            return None  # negacja zbioru -> brak czystego not(...) w DjangoQL
        return frag


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

    _DJANGOQL_OGOLNY = {
        "artykuł": const.CHARAKTER_OGOLNY_ARTYKUL,
        "rozdział": const.CHARAKTER_OGOLNY_ROZDZIAL,
        "książka": const.CHARAKTER_OGOLNY_KSIAZKA,
        "inne": const.CHARAKTER_OGOLNY_INNE,
    }

    def to_djangoql(self, value, operation):
        kod = self._DJANGOQL_OGOLNY.get(value)
        if kod is None:
            return None
        op = "!=" if str(operation) in {str(o) for o in DIFFERENT_ALL} else "="
        return f'charakter_formalny.charakter_ogolny {op} "{kod}"'


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

    def value_to_web(self, value):
        """Zmapuj zapisaną wartość na DOKŁADNĄ etykietę z listy wyboru.

        Pole jest typu VALUE_LIST — widget multiseeka ustawia ``select.val()``,
        więc zapisana wartość musi równać się jednej z opcji (``values``), a te
        są etykietami MPTT z prefiksem poziomu (i wiodącą spacją). Gdy w boxie
        ląduje samo ``nazwa`` (np. z „klik w charakter" na stronie autora),
        bez tego mapowania select nie trafia w żadną opcję i pole jest puste —
        mimo że samo wyszukiwanie działa (``value_from_web`` zdejmuje prefiks).
        """
        obj = self.value_from_web(value)
        if obj is None:
            return value
        return self.label_from_instance(obj)

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
        if value is None:
            return Q(pk__isnull=True)  # Return empty result for invalid filter value

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

    def to_djangoql(self, value, operation):
        """charakter_z_podrzednymi__rel (MPTT: sam + potomkowie) — dokładne."""
        obj = self.value_from_web(value)
        if obj is None:
            return None
        op = str(operation)
        diff = {str(o) for o in DIFFERENT_ALL}
        if op in diff:
            rel_op = "!="
        elif op in {str(o) for o in EQUALITY_OPS_ALL} - diff:
            rel_op = "="
        else:
            return None
        label = str(obj.nazwa).replace("\\", "\\\\").replace('"', '\\"')
        return f'charakter_z_podrzednymi__rel {rel_op} "{label} [{obj.pk}]"'


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

    _DJANGOQL_TK = {
        "krajowa": Konferencja.TK_KRAJOWA,
        "międzynarodowa": Konferencja.TK_MIEDZYNARODOWA,
        "lokalna": Konferencja.TK_LOKALNA,
    }

    def to_djangoql(self, value, operation):
        tk = self._DJANGOQL_TK.get(value)
        if tk is None:
            return None
        op = "!=" if str(operation) in {str(o) for o in DIFFERENT_ALL} else "="
        return f"konferencja.typ_konferencji {op} {tk}"
