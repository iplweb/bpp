from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit, Hidden
from django.forms import ModelForm

from import_dyscyplin.models import Import_Dyscyplin


class Import_DyscyplinForm(ModelForm):
    class Meta:
        fields = ("plik", "rok")
        model = Import_Dyscyplin

    def __init__(self, *args, **kw):
        super(Import_DyscyplinForm, self).__init__(*args, **kw)
        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                'Zaimportuj plik',
                'plik',
                'rok',
                Hidden('web_page_uid', ''),
                Submit('submit', 'Wyślij', css_id='id_submit')
            ))
        self.helper = helper
