"""``DynamicColumnsMixin`` z konfiguracją kolumn czytaną raz na request.

Pakiet ``dynamic_admin_columns`` przy KAŻDYM wywołaniu ``get_list_display``
szuka od nowa wiersza ``ModelAdmin`` użytkownika, wiersza globalnego
(``get_or_create``) i jego włączonych kolumn. Django woła
``get_list_display`` kilka razy na jedno wyświetlenie changelisty
(``get_changelist_instance``, ``get_sortable_by``,
``get_list_select_related``, do tego eksport i ``changelist_view``
pakietu), więc konfiguracja kolumn była czytana ~13 razy na request.

Ta wersja ładuje wiersz(e) ``ModelAdmin`` razem z kolumnami jednym
zapytaniem (+ prefetch) i trzyma wynik na obiekcie ``request`` — kolejne
wywołania w tym samym requeście nie pytają bazy. Semantyka bez zmian:
osobisty układ użytkownika ma pierwszeństwo, w przeciwnym razie układ
globalny; ``list_display_always`` zawsze na początku.

Dodatkowo pierwsze wyświetlenie changelisty w każdym procesie workera
wołało ``ModelAdmin.objects.enable``, które robi ``get_or_create`` dla
KAŻDEJ kolumny (~80 zapytań dla ``Wydawnictwo_Ciagle``). Tu najpierw
sprawdzamy dwoma zapytaniami, czy globalny układ w bazie ma już dokładnie
te kolumny, które ``enable`` by założył/zostawił — jeśli tak, ``enable``
byłby no-opem i go pomijamy.
"""

import re

from django.conf import settings
from django.contrib.admin import ModelAdmin as DjangoModelAdmin
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Prefetch, Q
from django.utils.datastructures import OrderedSet
from django.utils.functional import cached_property
from dynamic_admin_columns.mixins import DynamicColumnsMixin
from dynamic_admin_columns.models import ModelAdmin, ModelAdminColumn, _check_allowed
from dynamic_admin_columns.util import qual

_REQUEST_CACHE_ATTR = "_bpp_dynamic_columns_rows"
_COLUMNS_ATTR = "_bpp_columns"


class BppDynamicColumnsMixin(DynamicColumnsMixin):
    @cached_property
    def _modeladmin_enabled(self):
        cname = qual(self.__class__)
        _check_allowed(cname)
        row = ModelAdmin.objects.filter(
            user=None,
            class_name=cname,
            model_ref=ContentType.objects.get_for_model(self.model),
        ).first()
        if row is not None:
            existing = set(row.modeladmincolumn_set.values_list("col_name", flat=True))
            if existing == self._dyncol_expected_global_columns():
                return row
        return ModelAdmin.objects.enable(self)

    def _dyncol_expected_global_columns(self):
        """Zbiór kolumn, jaki ``ModelAdminManager.enable`` zostawi w bazie.

        Lustro logiki z ``dynamic_admin_columns.models.ModelAdminManager
        .enable``. Gdyby pakiet ją zmienił, a ta kopia nie, skutkiem jest
        co najwyżej niepotrzebne wywołanie ``enable`` (zbiory się różnią),
        a nie zły układ kolumn.
        """
        list_display = getattr(self, "list_display", [])
        if list_display == DjangoModelAdmin.list_display:
            if getattr(self, "list_display_always", []):
                list_display = []

        forbidden = getattr(self, "list_display_forbidden", []) + getattr(
            settings, "DYNAMIC_ADMIN_COLUMNS_FORBIDDEN_COLUMN_NAMES", []
        )
        always = getattr(self, "list_display_always", [])

        def column_allowed(field_name):
            if field_name in always:
                return False
            return not any(re.match(pattern, field_name) for pattern in forbidden)

        ret = set()
        for source in (
            list_display,
            getattr(self, "list_display_default", []),
            getattr(self, "list_display_allowed", []),
        ):
            if source == "__all__":
                source = [field.name for field in self.model._meta.fields]
            ret.update(col for col in source if column_allowed(col))
        return ret

    def _dyncol_effective_row(self, request):
        if request is None:
            return super()._dyncol_effective_row(request)

        cache = request.__dict__.setdefault(_REQUEST_CACHE_ATTR, {})
        try:
            return cache[self]
        except KeyError:
            row = cache[self] = self._dyncol_load_effective_row(request)
            return row

    def _dyncol_load_effective_row(self, request):
        # Jak w pakiecie: zainicjuj układ globalny (no-op po pierwszym
        # wywołaniu w procesie — ``cached_property``).
        self._modeladmin_enabled  # noqa: B018

        cname = qual(self.__class__)
        _check_allowed(cname)
        ct = ContentType.objects.get_for_model(self.model)

        user = getattr(request, "user", None)
        owner = Q(user__isnull=True)
        if user is not None and getattr(user, "is_authenticated", False):
            owner |= Q(user=user)

        rows = list(
            ModelAdmin.objects.filter(owner, class_name=cname, model_ref=ct)
            .order_by(F("user_id").asc(nulls_last=True))
            .prefetch_related(
                Prefetch(
                    "modeladmincolumn_set",
                    queryset=ModelAdminColumn.objects.order_by("ordering", "pk"),
                    to_attr=_COLUMNS_ATTR,
                )
            )
        )
        # Osobisty układ (user_id IS NOT NULL) ma pierwszeństwo przed
        # globalnym (NULL w ``user_id``) — stąd ``nulls_last``.
        if rows:
            return rows[0]

        # Brak wiersza globalnego w bazie — ścieżka pakietu (get_or_create).
        row = ModelAdmin.objects.db_repr_for_user(self, user)
        setattr(
            row,
            _COLUMNS_ATTR,
            list(row.modeladmincolumn_set.order_by("ordering", "pk")),
        )
        return row

    def get_list_display(self, request):
        row = self._dyncol_effective_row(request)
        columns = getattr(row, _COLUMNS_ATTR, None)
        if columns is None:
            return super().get_list_display(request)

        ret = OrderedSet(getattr(self, "list_display_always", []))
        for column in columns:
            if column.enabled:
                ret.add(column.col_name)
        return ret
