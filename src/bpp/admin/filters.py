# -*- encoding: utf-8 -*-
from django.contrib.admin.filters import SimpleListFilter

from bpp.models.struktura import Jednostka


class SimpleIntegerFilter(SimpleListFilter):
    db_field_name = None

    def lookups(self, request, model_admin):
        return [
            ("brak", "wartość nie ustalona"),
            ("zero", "zero"),
            ("powyzej", "więcej, niż zero"),
        ]

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


class SimpleNotNullFilter(SimpleListFilter):
    db_field_name = None

    def lookups(self, request, model_admin):
        return [("brak", "wartość nie ustalona"), ("jest", "wartość ustalona")]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            return queryset.filter(**{field: None})
        elif v == "jest":
            return queryset.exclude(**{field: None})

        return queryset


class LiczbaZnakowFilter(SimpleIntegerFilter):
    title = "liczba znaków wydawniczych"
    parameter_name = "liczba_znakow_wydawniczych"


class DOIUstawioneFilter(SimpleNotNullFilter):
    title = "DOI ustawione"
    parameter_name = "doi"


class PBNIDObecnyFilter(SimpleNotNullFilter):
    title = "PBN ID"
    parameter_name = "pbn_id"


class OrcidObecnyFilter(SimpleNotNullFilter):
    title = "ORCID"
    parameter_name = "orcid"


class PeselMD5ObecnyFilter(SimpleNotNullFilter):
    title = "PESEL MD5"
    parameter_name = "pesel_md5"


class CalkowitaLiczbaAutorowFilter(SimpleIntegerFilter):
    title = "całkowita liczba autorów"
    parameter_name = "calkowita_liczba_autorow"


class JednostkaFilter(SimpleListFilter):
    title = "Jednostka"
    parameter_name = "jednostka"

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            return queryset.filter(aktualna_jednostka_id=v)
        return queryset

    def lookups(self, request, model_admin):
        return (
            (x.pk, str(x)) for x in Jednostka.objects.all().select_related("wydzial")
        )
