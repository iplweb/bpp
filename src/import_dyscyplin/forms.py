from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Fieldset, Hidden, Layout, Submit
from django.forms import ModelForm, inlineformset_factory

from import_dyscyplin.models import Import_Dyscyplin, Kolumna


class Import_Dyscyplin_KolumnaForm(ModelForm):
    class Meta:
        model = Import_Dyscyplin
        fields = [
            "web_page_uid",
        ]

    def __init__(self, *args, **kw):
        super(Import_Dyscyplin_KolumnaForm, self).__init__(*args, **kw)
        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Hidden("web_page_uid", ""),
        )
        self.helper = helper


class KolumnaForm(ModelForm):
    class Meta:
        model = Kolumna
        fields = ["nazwa_w_pliku", "rodzaj_pola"]


class KolumnaFormSetHelper(FormHelper):
    template = "bootstrap/table_inline_formset.html"

    def __init__(self, *args, **kwargs):
        super(KolumnaFormSetHelper, self).__init__(*args, **kwargs)
        self.form_method = "post"
        self.add_input(
            Submit("submit", "Zatwierdź i przejdź dalej", css_class="button success")
        )
        self.render_required_fields = True


KolumnaFormSet = inlineformset_factory(
    Import_Dyscyplin, Kolumna, form=KolumnaForm, can_delete=False, extra=0
)


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
                "Zaimportuj plik",
                "plik",
                "rok",
                Hidden("web_page_uid", ""),
                Submit("submit", "Wyślij", css_id="id_submit"),
            )
        )
        self.helper = helper
