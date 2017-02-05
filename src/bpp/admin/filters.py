# -*- encoding: utf-8 -*-
from django.contrib.admin.filters import SimpleListFilter


class LiczbaZnakowFilter(SimpleListFilter):
    title = 'liczba znaków wydawniczych'
    parameter_name = 'liczba_znakow_wydawniczych'

    def lookups(self, request, model_admin):
        return (
            ('brak', 'wartość nie ustalona'),
            ('zero', 'zero'),
            ('powyzej', 'więcej, niż zero')
        )

    def queryset(self, request, queryset):
        v = self.value()

        if v == "brak":
            return queryset.filter(liczba_znakow_wydawniczych=None)
        elif v == "zero":
            return queryset.filter(liczba_znakow_wydawniczych=0)
        elif v == "powyzej":
            return queryset.filter(liczba_znakow_wydawniczych__gt=0)

        return queryset
