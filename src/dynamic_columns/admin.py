from adminsortable2.admin import SortableAdminMixin
from django.core.exceptions import FieldDoesNotExist

from dynamic_columns.models import ModelAdminColumn

from django.contrib import admin
from django.contrib.admin import ModelAdmin as DjangoModelAdmin
from django.contrib.admin.utils import NotRelationField, get_model_from_relation


@admin.action(description="Włącz wybrane opcje")
def make_enabled(modeladmin, request, queryset):
    queryset.update(enabled=True)


@admin.action(description="Wyłącz wybrane opcje")
def make_disabled(modeladmin, request, queryset):
    queryset.update(enabled=False)


@admin.register(ModelAdminColumn)
class ModelAdminColumnAdmin(SortableAdminMixin, DjangoModelAdmin):

    ordering = ["ordering"]
    list_filter = ["parent", "enabled"]
    list_display = ["col_parent", "col_verbose_name", "enabled", "ordering"]
    readonly_fields = ["parent", "col_name", "ordering"]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    actions = [make_disabled, make_enabled]

    def col_parent(self, obj: ModelAdminColumn):
        class_ = obj.parent.model_ref.model_class()
        return class_._meta.verbose_name

    col_parent.short_description = "Model name"

    def col_verbose_name(self, obj: ModelAdminColumn):
        model = obj.parent.model_ref.model_class()

        try:
            field = model._meta.get_field(obj.col_name)
        except FieldDoesNotExist:
            # Nie ma takiego pola. Może to być callable model_admin
            callable = None
            try:
                callable = getattr(obj.parent.class_ref, obj.col_name)
            except AttributeError:
                return obj.col_name

            if callable:
                try:
                    return callable.short_description
                except AttributeError:
                    return obj.col_name

        ret = obj.col_name
        if hasattr(field, "verbose_name") and field.verbose_name != obj.col_name:
            ret = field.verbose_name
        else:
            try:
                other_model = get_model_from_relation(field)
                ret = other_model._meta.verbose_name
            except NotRelationField:
                pass

        return ret

    col_verbose_name.short_description = "Column name"
