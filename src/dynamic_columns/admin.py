from builtins import callable

from adminsortable2.admin import SortableAdminMixin
from django.core.exceptions import FieldDoesNotExist

from dynamic_columns.models import ModelAdminColumn

from django.contrib import admin
from django.contrib.admin import ModelAdmin as DjangoModelAdmin
from django.contrib.admin.utils import NotRelationField, get_model_from_relation

from django.utils.translation import gettext_lazy as _


@admin.action(description=_("Enable selected columns"))
def make_enabled(modeladmin, request, queryset):
    queryset.update(enabled=True)


@admin.action(description=_("Disable selected columns"))
def make_disabled(modeladmin, request, queryset):
    queryset.update(enabled=False)


@admin.register(ModelAdminColumn)
class ModelAdminColumnAdmin(SortableAdminMixin, DjangoModelAdmin):

    ordering = ["ordering"]
    list_filter = ["parent", "enabled"]
    list_display = ["col_parent_name", "col_verbose_name", "enabled", "ordering"]
    readonly_fields = ["parent", "col_name", "ordering"]
    actions = [make_disabled, make_enabled]

    def has_delete_permission(self, request, obj=None):
        # By default ModelAdminColumns are managed automatically, so there is no
        # need to delete them
        return False

    def has_add_permission(self, request):
        # See ``self.has_delete_permission`` comment
        return False

    def col_parent_name(self, obj: ModelAdminColumn):
        """Verbose name of model in column's ModelAdmin"""
        class_ = obj.parent.model_ref.model_class()
        return class_._meta.verbose_name

    col_parent_name.short_description = _("Model admin name")

    def col_verbose_name(self, obj: ModelAdminColumn):
        """Get verbose name of ModelAdminColumn using various strategies"""
        model = obj.parent.model_ref.model_class()

        # If obj.col_name is a field, use its name later:
        try:
            field = model._meta.get_field(obj.col_name)
        except FieldDoesNotExist:
            # This is not a field. This could be Django's ModelAdmin callable
            model_admin_callable = None
            try:
                # Try getting that callable.
                model_admin_callable = getattr(obj.parent.class_ref, obj.col_name)
            except AttributeError:
                # If callable does not exists, return just the name of the column. There
                # is no such field and no such callable - maybe this is a problem with
                # non-existent column name?
                return obj.col_name

            if model_admin_callable and callable(model_admin_callable):
                # It is a function. Does it have a short_description?
                try:
                    return model_admin_callable.short_description
                except AttributeError:
                    # It is a function, but it does not have ``short_description``
                    # attribute. Let's return the col_name then:
                    return obj.col_name

        # It is a field!
        ret = obj.col_name

        if (
            hasattr(field, "verbose_name")
            and field.verbose_name
            and field.verbose_name != obj.col_name
        ):
            # Does it have a non-empty ``verbose_name`` attribute?
            ret = field.verbose_name
        else:
            # It does not have a ``verbose_name`` attribute.
            # Is it a ForeignKeyField?
            other_model = None
            try:
                other_model = get_model_from_relation(field)
            except NotRelationField:
                pass

            if other_model:
                # It is a ForeignKey! Does it have ``verbose_name``?
                try:
                    ret = other_model._meta.verbose_name
                except AttributeError:
                    pass

        return ret

    col_verbose_name.short_description = _("Column name")
