from django.contrib import admin

from formdefaults.models import FormRepresentation, FormFieldRepresentation


# Register your models here.


class FormFieldRepresentationInline(admin.TabularInline):
    model = FormFieldRepresentation
    fields = ["name", "label", "value", "user"]
    extra = 0


@admin.register(FormRepresentation)
class FormRepresentationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "label"]
    inlines = [
        FormFieldRepresentationInline,
    ]
    readonly_fields = list_display
