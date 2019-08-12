from django import forms
from django.contrib import admin

from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Poziom_WydawcyInlineForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kw):
        super(Poziom_WydawcyInlineForm, self).__init__(*args, **kw)
        if kw.get('instance'):
            self.fields['rok'].disabled = True


class Poziom_WydawcyInline(admin.TabularInline):
    model = Poziom_Wydawcy
    form = Poziom_WydawcyInlineForm
    extra = 1
    pass


@admin.register(Wydawca)
class WydawcaAdmin(admin.ModelAdmin):
    search_fields = ['nazwa']
    inlines = [Poziom_WydawcyInline, ]
    pass
