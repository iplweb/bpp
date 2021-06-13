# -*- encoding: utf-8 -*-
from django.db.models import F, IntegerField, Max
from django.db.models.functions import Cast

from django.contrib.admin.filters import SimpleListFilter
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType

from bpp.models import BppUser
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


class OrcidAutoraDyscyplinyObecnyFilter(SimpleNotNullFilter):
    title = "ORCID autora"
    parameter_name = "autor__orcid"


class PBN_UID_IDAutoraObecnyFilter(SimpleNotNullFilter):
    title = "PBN UID autora"
    parameter_name = "autor__pbn_uid_id"


class PBN_UID_IDObecnyFilter(SimpleNotNullFilter):
    title = "PBN UID"
    parameter_name = "pbn_uid_id"


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


class LogEntryFilterBase(SimpleListFilter):
    action_flags = [ADDITION, CHANGE]

    def __init__(self, request, params, model, model_admin):
        self.content_type = ContentType.objects.get_for_model(model)
        super(LogEntryFilterBase, self).__init__(
            request=request, params=params, model=model, model_admin=model_admin
        )

    def logentries(self):
        return LogEntry.objects.filter(
            action_flag__in=self.action_flags,
            content_type_id=self.content_type,
        )

    def lookups(self, request, model_admin):
        return (
            (x.pk, x.username)
            for x in BppUser.objects.filter(
                pk__in=self.logentries().values_list("user_id")
            ).only("pk", "username")
        )


class OstatnioZmienionePrzezFilter(LogEntryFilterBase):
    title = "Ostatnio zmieniony przez"
    parameter_name = "ostatnio_zmieniony_przez"

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            res = (
                self.logentries()
                .values("object_id", "content_type_id")
                .annotate(
                    max_action_time=Max("action_time"),
                    max_pk=F("object_id"),
                    max_user=F("user_id"),
                )
                .filter(max_user=v)
                .values_list(Cast("object_id", IntegerField()))
            )

            return queryset.filter(pk__in=res)
        return queryset


class UtworzonePrzezFilter(LogEntryFilterBase):
    title = "Utworzone przez"
    parameter_name = "utworzone_przez"

    action_flags = [ADDITION]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            res = (
                self.logentries()
                .filter(user_id=v)
                .values_list(Cast("object_id", IntegerField()))
            )

            return queryset.filter(pk__in=res)
        return queryset
