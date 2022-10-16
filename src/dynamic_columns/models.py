"""Models for in-database representation of dynamic admin columns configuration.
"""
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
from django.utils.translation import gettext_lazy as _


class ModelAdminManager(models.Manager):
    def db_repr(self, model_admin: DjangoModelAdmin) -> "ModelAdmin":
        """
        Get database representation of a Django's ModelAdmin -- return
        a class ``dynamic_columns.models.ModelAdmin``. This class basically
        consists of 2 elements:

        * full qualified class name of ``model_admin``,
        * django.contrib.contenttype.models.ContentType reference of model registered
          for that model_admin instance.

        :param model_admin: ``django.contrib.admin.admin.ModelAdmin`` instance.

        :return: ``dynamic_columns.models.ModelAdmin`` instance, created fresh or from
        database.
        """
        cname = qual(model_admin.__class__)

        found = False
        for path in getattr(settings, "DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS", []):
            if cname.startswith(path):
                found = True

        if not found:
            raise CodeAccessNotAllowed(
                f"Please add {cname} to your project's settings.py if you want to "
                f"use DynamicColumnsMixin for your {model_admin} classes -- "
                f"add it to a list ``DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS``. "
            )

        return self.get_or_create(
            class_name=cname,
            model_ref=ContentType.objects.get_for_model(model_admin.model),
        )[0]

    def enable(self, model_admin: DjangoModelAdmin) -> "ModelAdmin":
        """
        Enable dynamic columns -- create an in-database representation
        of Django's ModelAdmin instance, create in-database representation
        of columns: enabled by default, which can be moved or disabled by end-user
        (``model_admin.list_display_default``) and disabled by default, which
        can be later enabled by end-user (``model_admin.list_display_allowed``),
        keeping forbidden columns (``model_admin.list_display_forbidden``) away.

        :returns: dynamic_columns.models.ModelAdmin
        """
        obj = self.db_repr(model_admin)

        # If there is a ``list_display`` setting on ``model_admin``, treat it
        # as ``list_display_default``.
        #
        # Unless it was not changed from the default settings, which at
        #  the time of this writing, contains only "__str__".
        #
        # In this case, if ``list_display_always`` is declared, we will skip it,
        # but it is not declared - we will not.
        #
        # This way we can still support the "old" ``list_display`` parameter, but avoid
        # displaying double columns in case it is not actually being used, in favor
        # of the new ``list_display_default`` and ``list_display_always``.
        #

        list_display = getattr(model_admin, "list_display", [])
        if list_display == DjangoModelAdmin.list_display:
            # Looks like ``list_display`` was not changed from default setting.
            # Is there ``list_display_always`` declared? If yes, empty
            # ``list_display`` variable
            if getattr(model_admin, "list_display_always", []):
                list_display = []

        # Sources of column names. ``list_display``, handled in a way described
        # above, ``list_display_default`` -- columns visible by default,
        # and ``list_display_allowed`` -- columns not visible by default, but
        # can be enabled later:

        column_sources = [
            # (column_source, column_enabled_defualt_value)
            (list_display, True),
            (getattr(model_admin, "list_display_default", []), True),
            (getattr(model_admin, "list_display_allowed", []), False),
        ]

        # Did you know, that instead of typing all the column names by yourself,
        # you could use a magic string "__all__"? This way you can get all the
        # columns in the model. But, could it be too broad? It could be. This is
        # why there is a setting ``list_display_forbidden`` which can exclude
        # some columns on a per-model basis, and there is also a configuration setting
        # ``DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES``. Both those variables can
        # contain a list of regex that will be matched against column names.

        forbidden_columns_patterns = (
            # ``list_display_always`` are forbidden in the database - they are declared
            # in the code, they cannot be moved:
            getattr(model_admin, "list_display_forbidden", [])
            + getattr(settings, "DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES", [])
        )

        list_display_always = getattr(model_admin, "list_display_always", [])

        def column_allowed(field_name):
            if field_name in list_display_always:
                return False

            for elem in forbidden_columns_patterns:
                if re.match(elem, field_name):
                    return False

            return True

        all_columns = set()

        db_max = ModelAdminColumn.objects.all().aggregate(max_cnt=Max("ordering"))
        cnt = (db_max["max_cnt"] or 0) + 1

        for column_source, default_value in column_sources:
            if column_source == "__all__":
                # Discover "all" columns
                columns = [
                    field.name
                    for field in model_admin.model._meta.fields
                    if column_allowed(field.name)
                ]
            else:
                # Got an exact list of column names in the source code:
                columns = column_source

            for column in [col for col in columns if column_allowed(col)]:
                all_columns.add(column)
                cnt += 1
                obj.modeladmincolumn_set.get_or_create(
                    col_name=column,
                    defaults={"ordering": cnt, "enabled": default_value},
                )

        # Remove stale columns from the database
        obj.modeladmincolumn_set.exclude(col_name__in=all_columns).delete()

        return obj


class ModelAdmin(models.Model):
    """
    In-database representation of a Django's ModelAdmin.

    Consists of 2 parameters actually.

    ``class_name`` is the class name of a Django's ModelAdmin,

    ``model_ref`` is a django.contrib.contenttypes.models.ContentType reference
    to a content type that is registered for that admin.

    In Django you can register a single ModelAdmin class for different models.
    This is no different here. You can create ModelAdmins with the same ``class_name``
    but for different ``model_ref``s and have different columns visible for every
    single one.
    """

    class_name = models.TextField()

    model_ref = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    objects = ModelAdminManager()

    class Meta:
        unique_together = [("class_name", "model_ref")]
        ordering = ("class_name",)
        verbose_name = _("Model admin")
        verbose_name_plural = _("Model admins")

    def __str__(self):
        return self.class_name

    @cached_property
    def class_ref(self):
        """
        This function returns a reference to Django's ModelAdmin class, preferably
        the one from your project's code. But as the database could get modified
        in an unsafe manner, we will check if the module path for that ModelAdmin
        is defined in settings.py's ``DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS``.
        """
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
        """This function returns the list of columns, in a specific order
        that should be displayed in a Django ModelAdmin's change list.
        """
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
    """This is an in-database column representation of a given
    in-database ModelAdmin instance.

    It can be enabled or disabled -- visible or invisible.

    It also has an order in which it is displayed.
    """

    parent = models.ForeignKey(
        ModelAdmin, on_delete=models.CASCADE, verbose_name=_("Parent")
    )

    col_name = models.CharField(max_length=255, verbose_name=_("Column name"))

    enabled = models.BooleanField(default=True, verbose_name=_("Enabled"))
    ordering = models.PositiveSmallIntegerField(verbose_name=_("Ordering"))

    def __str__(self):
        ret = _("Column") + f' "{self.col_name}"'

        if self.parent_id:
            ret += _(" of model ") + f'"{self.parent.class_name}"'

        return ret

    class Meta:
        unique_together = [("parent", "col_name")]
        ordering = ("parent", "ordering")
        verbose_name = _("Model admin column")
        verbose_name_plural = _("Model admin columns")
