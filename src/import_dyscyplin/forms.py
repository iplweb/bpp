from django.forms import ModelForm


class Import_DyscyplinForm(ModelForm):
    class Meta:
        fields = ("plik", "rok")
