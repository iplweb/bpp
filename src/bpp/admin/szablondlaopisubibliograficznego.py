from django.contrib import admin

from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego


@admin.register(SzablonDlaOpisuBibliograficznego)
class SzablonDlaOpisuBibliograficznegoAdmin(admin.ModelAdmin):
    list_display = ["model", "template"]
    empty_value_display = "(każdy)"
