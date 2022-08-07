from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from dal import autocomplete
from django import forms
from django.forms import inlineformset_factory
from django.forms.widgets import HiddenInput

from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    Zgloszenie_Publikacji_Plik,
)

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka


class Zgloszenie_Publikacji_DaneOgolneForm(forms.ModelForm):

    tytul_oryginalny = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "cols": 80})
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "tytul_oryginalny",
            "rok",
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
                "rok",
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


class Zgloszenie_Publikacji_AutorForm(forms.ModelForm):
    class Media:
        js = ["/static/bpp/js/autorform_dependant.js"]

    class Meta:
        model = Zgloszenie_Publikacji_Autor
        fields = ["autor", "jednostka", "dyscyplina_naukowa", "rok"]

    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:public-autor-autocomplete"),
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.publiczne(),
        widget=autocomplete.ModelSelect2(url="bpp:public-jednostka-autocomplete"),
    )

    dyscyplina_naukowa = forms.ModelChoiceField(
        queryset=Dyscyplina_Naukowa.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:dyscyplina-autocomplete",
            forward=["autor", "rok"],
        ),
    )

    rok = forms.IntegerField(widget=HiddenInput)

    # delete = forms.BooleanField(
    #     label="Kliknij i zapisz, aby usunąć", widget=forms.CheckboxInput, required=False
    # )

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Autor",
                "autor",
                "jednostka",
                "dyscyplina_naukowa",
                "rok",  # "delete"
            )
        )
        super().__init__(*args, **kw)


Zgloszenie_Publikacji_AutorFormSet = inlineformset_factory(
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    form=Zgloszenie_Publikacji_AutorForm,
    extra=1,
)

Zgloszenie_Publikacji_PlikFormSet = inlineformset_factory(
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Plik,
    fields=[
        "plik",
    ],
    # widgets={"plik": FileInput()},
    extra=3,
    can_delete=False,
    # can_delete_extra=False,
)


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
