from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms

from zglos_publikacje.models import Zgloszenie_Publikacji


class Zgloszenie_Publikacji_KosztPublikacjiForm(forms.ModelForm):
    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "opl_pub_cost_free",
            "opl_pub_research_potential",
            "opl_pub_research_or_development_projects",
            "opl_pub_other",
            "opl_pub_amount",
        ]

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Opłata za publikację",
                "opl_pub_cost_free",
                "opl_pub_research_potential",
                "opl_pub_research_or_development_projects",
                "opl_pub_other",
                "opl_pub_amount",
            ),
        )
        super().__init__(*args, **kw)

    def clean_opl_pub_cost_free(self):
        v = self.cleaned_data.get("opl_pub_cost_free")
        if v is None:
            raise forms.ValidationError("Wybierz jakąś wartość")
        return v


class Zgloszenie_Publikacji_DaneOgolneForm(forms.ModelForm):

    tytul_oryginalny = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "cols": 80})
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "tytul_oryginalny",
            "doi",
            "public_www",
            "public_dostep_dnia",
            "www",
            "dostep_dnia",
            "email",
        ]

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Informacje o publikacji",
                "tytul_oryginalny",
                "doi",
                Row(
                    Column("www", css_class="large-8 small-12"),
                    Column("dostep_dnia", css_class="large-4 small-12"),
                ),
                Row(
                    Column("public_www", css_class="large-8 small-12"),
                    Column("public_dostep_dnia", css_class="large-4 small-12"),
                ),
                "email",
            ),
        )
        super().__init__(*args, **kw)
