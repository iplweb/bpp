from django.contrib import admin

from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego
from bpp.util import rebuild_instances_of_models


@admin.register(SzablonDlaOpisuBibliograficznego)
class SzablonDlaOpisuBibliograficznegoAdmin(admin.ModelAdmin):
    list_display = ["model", "template"]
    empty_value_display = "(każdy)"

    def save_model(self, request, obj: SzablonDlaOpisuBibliograficznego, form, change):
        super(SzablonDlaOpisuBibliograficznegoAdmin, self).save_model(
            request, obj, form, change
        )
        rebuild_instances_of_models(obj.get_models_for_this_szablon())

    def delete_model(self, request, obj: SzablonDlaOpisuBibliograficznego):
        super(SzablonDlaOpisuBibliograficznegoAdmin, self).delete_model(request, obj)
        rebuild_instances_of_models(
            SzablonDlaOpisuBibliograficznego.objects.all_templated_models
        )
