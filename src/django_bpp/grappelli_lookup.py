"""Widoki lookupów grappelli z kontrolą uprawnień.

Oryginalne widoki ``grappelli.views.related`` sprawdzają wyłącznie
``is_staff``. Tu dokładamy:

- dostęp tylko do modeli zarejestrowanych w ``admin.site``, dla których
  użytkownik ma uprawnienie podglądu (``ModelAdmin.has_view_permission``),
- queryset budowany przez ``ModelAdmin.get_queryset(request)``,
- walidację ``query_string`` (``limit_choices_to`` widżetów) — dopuszczalne
  są tylko pola bezpośrednio na modelu i proste lookupy,
- walidację ``to_field`` przez ``ModelAdmin.to_field_allowed``.

Trasy są rejestrowane w ``django_bpp/urls.py`` przed ``grappelli.urls``,
pod tymi samymi adresami.
"""

from urllib.parse import unquote

from django.contrib import admin
from django.contrib.admin.utils import prepare_lookup_value
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db.models.constants import LOOKUP_SEP
from django.utils.encoding import smart_str
from grappelli.views.related import AutocompleteLookup, M2MLookup, RelatedLookup

DOZWOLONE_LOOKUPY = frozenset(
    {"exact", "iexact", "in", "isnull", "gt", "gte", "lt", "lte"}
)

WRAZLIWE_FRAGMENTY_NAZW = ("password", "token", "secret")

WRAZLIWE_APLIKACJE = frozenset({"oauth2_provider", "sessions", "axes"})

IGNOROWANE_PARAMETRY = frozenset({"_to_field", "_popup"})


def wrazliwa_nazwa(nazwa):
    nazwa = nazwa.lower()
    return any(fragment in nazwa for fragment in WRAZLIWE_FRAGMENTY_NAZW)


def wrazliwy_model(model):
    if model is None:
        return False
    if model._meta.app_label in WRAZLIWE_APLIKACJE:
        return True
    return model._meta.concrete_model is get_user_model()._meta.concrete_model


def znajdz_pole(model, nazwa):
    try:
        return model._meta.get_field(nazwa)
    except FieldDoesNotExist:
        for field in model._meta.concrete_fields:
            if field.attname == nazwa:
                return field
    return None


def klucz_filtra_dozwolony(model, klucz):
    """Czy klucz z ``query_string`` może trafić do ``qs.filter``.

    Dopuszczamy ``<pole>`` albo ``<pole>__<lookup>``, gdzie pole jest
    konkretną kolumną tego modelu (także ``<fk>``/``<fk>_id``), a lookup
    należy do ``DOZWOLONE_LOOKUPY``. Przechodzenie przez relacje jest
    zabronione.
    """
    czesci = klucz.split(LOOKUP_SEP)
    if len(czesci) > 2:
        return False

    nazwa = czesci[0]
    lookup = czesci[1] if len(czesci) == 2 else "exact"

    if lookup not in DOZWOLONE_LOOKUPY or wrazliwa_nazwa(nazwa):
        return False

    pole = znajdz_pole(model, nazwa)
    if pole is None or not getattr(pole, "concrete", False):
        return False
    if pole.many_to_many:
        return False
    if pole.is_relation and wrazliwy_model(pole.related_model):
        return False
    return True


class BezpiecznyLookupMixin:
    def get_model(self):
        super().get_model()
        self.model_admin = None
        if self.model is None:
            return None

        model_admin = admin.site._registry.get(self.model)
        if model_admin is None or not model_admin.has_view_permission(self.request):
            raise PermissionDenied

        to_field = self.GET.get("to_field", None)
        if to_field is not None and (
            wrazliwa_nazwa(to_field)
            or not model_admin.to_field_allowed(self.request, to_field)
        ):
            raise PermissionDenied

        self.model_admin = model_admin
        return self.model

    def get_filtered_queryset(self, qs):
        # Grappelli przekazuje tu ``_default_manager.get_queryset()``;
        # podmieniamy bazę na queryset z ModelAdmin (np. filtr uczelni).
        # Robimy to w tym miejscu, bo ``AutocompleteLookup.get_queryset``
        # woła ``RelatedLookup.get_queryset`` przez ``super()``.
        qs = self.model_admin.get_queryset(self.request)
        filters = {}
        query_string = self.GET.get("query_string", None)

        if query_string:
            for item in query_string.split(":"):
                if not item:
                    continue
                klucz, sep, wartosc = item.partition("=")
                if not sep:
                    raise PermissionDenied
                klucz = smart_str(klucz)
                if klucz in IGNOROWANE_PARAMETRY:
                    continue
                if not klucz_filtra_dozwolony(self.model, klucz):
                    raise PermissionDenied
                filters[klucz] = prepare_lookup_value(
                    klucz, unquote(smart_str(wartosc))
                )
        return qs.filter(**filters)


class BppRelatedLookup(BezpiecznyLookupMixin, RelatedLookup):
    pass


class BppM2MLookup(BezpiecznyLookupMixin, M2MLookup):
    pass


class BppAutocompleteLookup(BezpiecznyLookupMixin, AutocompleteLookup):
    def get_data(self):
        if self.model is None:
            return []
        return super().get_data()
