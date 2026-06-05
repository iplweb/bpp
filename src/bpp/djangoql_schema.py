"""Wspólny schemat DjangoQL dla BPP — auto-pickery ``<fk>__rel``.

Trzon współdzielony przez widok „Szukaj zapytaniem" (`bpp.views.zapytanie`) i
adminy z ``DjangoQLSearchMixin`` (ustawiają ``djangoql_schema = BppQLSchema``).

Idea: dla KAŻDEGO klucza obcego (FK) modelu, którego model docelowy ma
pole-etykietę (nazwa/skrot/tytuł/opis bibliograficzny…), auto-generujemy
„picker" pod nazwą ``<fk>__rel``. Wybierasz obiekt z podpowiedzi i filtruje po
jego pk (``lookup_name`` wskazuje realny FK), z fallbackiem free-text (icontains
po polach-etykietach). Notacja z kropką (``zrodlo.nazwa``) zostaje domyślna dla
FK — picker tylko ją uzupełnia.

Lookup nie podpowiada ukrytych: queryset filtruje boolowskie pola widoczności
(``widoczny``/``widoczna``/``widoczne``/``visible``/``enabled``/``pokazuj`` =
True, ``disabled``/``ukryty``… = False). FK do modeli bez pola-etykiety
(np. ``pbn_uid`` → ``Journal``) oraz rodzic ``rekord`` (cache/through) są
pomijane.
"""

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils.html import strip_tags
from djangoql.extras import AutocompleteField, ExtrasSchema

from bpp.models import Charakter_Formalny, Jednostka

#: Pola-etykiety wg priorytetu — czym opisać i po czym szukać obiekt w pickerze.
#: Opis bibliograficzny jako pierwszy: dla publikacji jest najczytelniejszy.
_LABEL_FIELDS = (
    "opis_bibliograficzny_cache",
    "nazwa",
    "skrot",
    "tytul_oryginalny",
    "nazwisko",
    "imiona",
    "kod",
)
#: Boolowskie pola widoczności: widoczne, gdy True.
_VISIBLE_WHEN_TRUE = (
    "widoczny",
    "widoczna",
    "widoczne",
    "visible",
    "enabled",
    "pokazuj",
)
#: Boolowskie pola „ukrycia": widoczne, gdy False.
_VISIBLE_WHEN_FALSE = ("disabled", "ukryty", "ukryta", "ukryte")
_REL_SUFFIX = "__rel"
#: FK pomijane (rodzic cache/through — pickowanie rodzica nie ma sensu).
_SKIP_FK = ("rekord",)
#: Wirtualne pole: picker po Jednostce dopasowujący rodzinę MPTT.
_SUBUNITS_FIELD = "jednostka_z_podjednostkami__rel"
#: Wirtualne pole: picker po Charakterze Formalnym dopasowujący MPTT-descendants.
_CHARAKTER_SUB_FIELD = "charakter_z_podrzednymi__rel"


def _field_names(model):
    return {f.name for f in model._meta.get_fields() if isinstance(f, models.Field)}


def _label_fields(model):
    """Pola-etykiety modelu (przecięcie z ``_LABEL_FIELDS``, wg priorytetu)."""
    names = _field_names(model)
    return [f for f in _LABEL_FIELDS if f in names]


def _is_bool_field(model, name):
    try:
        return isinstance(model._meta.get_field(name), models.BooleanField)
    except FieldDoesNotExist:
        return False


def _visible_qs(model):
    """Queryset modelu z odfiltrowanymi niewidocznymi pozycjami."""
    qs = model.objects.all()
    for name in _VISIBLE_WHEN_TRUE:
        if _is_bool_field(model, name):
            qs = qs.filter(**{name: True})
    for name in _VISIBLE_WHEN_FALSE:
        if _is_bool_field(model, name):
            qs = qs.filter(**{name: False})
    return qs


def _picker_label(model):
    """Callable ``obj -> etykieta`` dla pickera; dla publikacji preferuje opis
    bibliograficzny (bez HTML). ``None`` → AutocompleteField użyje ``str(obj)``."""
    if "opis_bibliograficzny_cache" in _field_names(model):

        def label(obj):
            return strip_tags(getattr(obj, "opis_bibliograficzny_cache", "") or "")

        return label
    return None


def _picker_fks(model):
    """FK (many_to_one) modelu nadające się na picker — model docelowy ma
    pole-etykietę i nie jest to pomijany rodzic ``rekord``."""
    out = []
    for f in model._meta.get_fields():
        if not (f.is_relation and getattr(f, "many_to_one", False)):
            continue
        if f.related_model is None or f.name in _SKIP_FK:
            continue
        if not _label_fields(f.related_model):
            continue
        out.append(f)
    return out


class JednostkaZPodjednostkamiField(AutocompleteField):
    """Picker po Jednostce: dopasowuje rekordy autorów z tej jednostki ORAZ
    wszystkich jednostek z jej rodziny MPTT (przodkowie+sama+potomkowie).

    Odwzorowuje multiseek EQUAL_PLUS_SUB_FEMALE:
        Q(autorzy__jednostka__in=value.get_family())
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            # free-text fallback po nazwie jednostki (best-effort), uwzględnia operator
            q = Q(autorzy__jednostka__nazwa__icontains=str(value))
            return ~q if operator in ("!=", "not in") else q
        try:
            jednostka = Jednostka.objects.get(pk=parsed)
        except Jednostka.DoesNotExist:
            # Pozytywne dopasowanie: nic nie pasuje. Negacja: pasuje wszystko.
            return Q() if operator in ("!=", "not in") else Q(pk__in=[])
        q = Q(autorzy__jednostka__in=jednostka.get_family())
        return ~q if operator in ("!=", "not in") else q


class CharakterZPodrzednymiField(AutocompleteField):
    """Picker po Charakter_Formalny: dopasowuje rekordy o tym charakterze ORAZ
    wszystkich potomkach w drzewie MPTT (sam + descendants).

    Odwzorowuje CharakterFormalnyQueryObject.real_query:
        Q(charakter_formalny__in=value.get_descendants(include_self=True))
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            q = Q(charakter_formalny__nazwa__icontains=str(value))
            return ~q if operator in ("!=", "not in") else q
        try:
            ch = Charakter_Formalny.objects.get(pk=parsed)
        except Charakter_Formalny.DoesNotExist:
            return Q() if operator in ("!=", "not in") else Q(pk__in=[])
        q = Q(charakter_formalny__in=ch.get_descendants(include_self=True))
        return ~q if operator in ("!=", "not in") else q


def _has_autorzy_jednostka(model):
    """True, gdy model ma odwrotną relację 'autorzy' z FK 'jednostka'
    (Rekord/cache)."""
    try:
        rel = model._meta.get_field("autorzy")
    except FieldDoesNotExist:
        return False
    related = getattr(rel, "related_model", None)
    if related is None:
        return False
    return "jednostka" in {
        f.name for f in related._meta.get_fields() if isinstance(f, models.Field)
    }


def _has_charakter_formalny(model):
    """True, gdy model ma FK 'charakter_formalny' (Rekord/cache)."""
    try:
        f = model._meta.get_field("charakter_formalny")
    except FieldDoesNotExist:
        return False
    return getattr(f, "many_to_one", False)


class RelPickerSchemaMixin:
    """Mixin auto-generujący pickery ``<fk>__rel`` (patrz docstring modułu)."""

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += [f.name + _REL_SUFFIX for f in _picker_fks(model)]
        if _has_autorzy_jednostka(model):
            fields.append(_SUBUNITS_FIELD)
        if _has_charakter_formalny(model):
            fields.append(_CHARAKTER_SUB_FIELD)
        return fields

    def get_field_instance(self, model, field_name):
        if field_name == _SUBUNITS_FIELD:
            return JednostkaZPodjednostkamiField(
                model=model,
                name=_SUBUNITS_FIELD,
                nullable=True,
                queryset=_visible_qs(Jednostka),
                search_fields=_label_fields(Jednostka),
            )
        if field_name == _CHARAKTER_SUB_FIELD:
            return CharakterZPodrzednymiField(
                model=model,
                name=_CHARAKTER_SUB_FIELD,
                nullable=True,
                queryset=_visible_qs(Charakter_Formalny),
                search_fields=_label_fields(Charakter_Formalny),
            )
        if field_name.endswith(_REL_SUFFIX):
            fk_name = field_name[: -len(_REL_SUFFIX)]
            try:
                fk = model._meta.get_field(fk_name)
            except FieldDoesNotExist:
                fk = None
            if fk is not None and fk.is_relation and fk.related_model is not None:
                related = fk.related_model
                return AutocompleteField(
                    model=model,
                    name=field_name,
                    lookup_name=fk_name,
                    nullable=getattr(fk, "null", False),
                    queryset=_visible_qs(related),
                    search_fields=_label_fields(related),
                    label=_picker_label(related),
                )
        return super().get_field_instance(model, field_name)


class BppQLSchema(RelPickerSchemaMixin, ExtrasSchema):
    """ExtrasSchema (agregaty + części dat) + auto-pickery ``<fk>__rel``.

    Wspólny dla widoku „Szukaj zapytaniem" i adminów (``djangoql_schema =
    BppQLSchema``). Mapa modeli jest budowana lazy per-model, więc ten sam
    schemat obsługuje dowolny model (Rekord, Autor, Wydawnictwo_*, Patent,
    Praca_Doktorska/Habilitacyjna, …).
    """
