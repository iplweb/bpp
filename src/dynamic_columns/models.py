import re

from django.conf import settings
from django.db import models
from django.db.models import Max

from dynamic_columns.exceptions import CodeAccessNotAllowed
from dynamic_columns.util import qual, str_to_class

from django.contrib.admin import ModelAdmin as DjangoModelAdmin
from django.contrib.contenttypes.models import ContentType

from django.utils.datastructures import OrderedSet
from django.utils.functional import cached_property


class ModelAdminManager(models.Manager):
    def db_repr(self, model_admin):
        return self.get_or_create(
            class_name=qual(model_admin.__class__),
            model_ref=ContentType.objects.get_for_model(model_admin.model),
        )[0]

    def enable(self, model_admin: "DjangoModelAdmin") -> "ModelAdmin":
        obj = self.db_repr(model_admin)

        list_display = getattr(model_admin, "list_display", [])
        if list_display == DjangoModelAdmin.list_display:
            list_display = []

        column_sources = [
            # (column_source, column_enabled_defualt_value)
            (list_display, True),
            (getattr(model_admin, "list_display_default", []), True),
            (getattr(model_admin, "list_display_allowed", []), False),
        ]

        exclude_from___all__ = (
            getattr(model_admin, "list_display_always", [])
            + getattr(model_admin, "list_display_forbidden", [])
            + getattr(settings, "DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES", [])
        )

        def suitable_for_all(field_name):
            for elem in exclude_from___all__:
                if re.match(elem, field_name):
                    return False
            return True

        all_columns = set()

        db_max = ModelAdminColumn.objects.all().aggregate(max_cnt=Max("ordering"))
        cnt = (db_max["max_cnt"] or 0) + 1

        for column_source, default_value in column_sources:
            if column_source == "__all__":
                columns = [
                    field.name
                    for field in model_admin.model._meta.fields
                    if suitable_for_all(field.name)
                ]
            else:
                columns = column_source

            for column in columns:
                all_columns.add(column)
                cnt += 1
                _obj, created = obj.modeladmincolumn_set.get_or_create(
                    col_name=column,
                    defaults={"ordering": cnt, "enabled": default_value},
                )

        # Remove stale columns
        obj.modeladmincolumn_set.exclude(col_name__in=all_columns).delete()

        return obj


class ModelAdmin(models.Model):
    class_name = models.TextField()

    model_ref = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    objects = ModelAdminManager()

    def __str__(self):
        return self.class_name

    @cached_property
    def class_ref(self):
        found = False
        for path in getattr(settings, "DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS", []):
            if self.class_name.startswith(path):
                found = True

        if not found:
            raise CodeAccessNotAllowed(
                f"Path {self.class_name} not found in settings.DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS"
            )
        return str_to_class(self.class_name)

    def get_list_display(self, model_admin, request):
        ret = OrderedSet()

        column_sources = [
            getattr(model_admin, "list_display_always", []),
            ModelAdmin.objects.db_repr(model_admin)
            .modeladmincolumn_set.filter(enabled=True)
            .values_list("col_name", flat=True),
        ]

        for column_source in column_sources:
            [ret.add(c) for c in column_source]

        return ret


class ModelAdminColumn(models.Model):
    parent = models.ForeignKey(ModelAdmin, on_delete=models.CASCADE)

    col_name = models.CharField(max_length=255)

    enabled = models.BooleanField(default=True)
    ordering = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = [("parent", "col_name")]
        ordering = ("parent", "ordering")
