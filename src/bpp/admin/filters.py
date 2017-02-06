# -*- encoding: utf-8 -*-
from django.contrib.admin.filters import SimpleListFilter


class SimpleIntegerFilter(SimpleListFilter):
    db_field_name = None

    def lookups(self, request, model_admin):
        return (
            ('brak', 'wartość nie ustalona'),
            ('zero', 'zero'),
            ('powyzej', 'więcej, niż zero')
        )

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            return queryset.filter(**{field: None})
        elif v == "zero":
            return queryset.filter(**{field: 0})
        elif v == "powyzej":
            return queryset.filter(**{field + "__gt": 0})

        return queryset


class LiczbaZnakowFilter(SimpleIntegerFilter):
    title = 'liczba znaków wydawniczych'
    parameter_name = 'liczba_znakow_wydawniczych'


class CalkowitaLiczbaAutorowFilter(SimpleIntegerFilter):
    title = 'całkowita liczba autorów'
    parameter_name = 'calkowita_liczba_autorow'
