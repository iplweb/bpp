from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Fieldset, Layout
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.widgets import HiddenInput

from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor
from zglos_publikacje.validators import validate_file_extension_pdf

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka


class Zgloszenie_Publikacji_DaneOgolneForm(forms.ModelForm):
    rok = forms.IntegerField(
        help_text="Rok publikacji zgłaszanej pracy. Rok na późniejszych etapach używany jest "
        "do ustalenia i zweryfikowania dyscyplin naukowych zgłoszonych przez autorów. "
    )

    tytul_oryginalny = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "cols": 80}),
        help_text="Tytuł pracy. Prosimy o wpisanie samego tytułu. Proszę nie wpisywać źródła, miejsca publikacji, "
        "autorów itp. -- wyłacznie tytuł pracy. ",
    )

    email = forms.EmailField(
        help_text="Prosimy o podanie poprawnego adresu e-mail. W razie problemów ze zgłoszeniem na ten adres "
        "zostanie skierowana dalsza korespondencja."
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "tytul_oryginalny",
            "rodzaj_zglaszanej_publikacji",
            "rok",
            "strona_www",
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
                "strona_www",
                "email",
            ),
        )
        super().__init__(*args, **kw)


class Zgloszenie_Publikacji_Plik(forms.ModelForm):
    plik = forms.FileField(
        required=False,
        help_text="""Ponieważ w poprzednim formularzu nie podano adresu WWW
    ani adresu DOI publikacji, prosimy o załączenie pełnego tekstu pracy w formacie PDF.
    Dodawany plik wyłącznie na potrzeby zarejestrowania rekordu w bazie publikacji -
    do wglądu Biblioteki; nie będzie dalej udostępniany.
""",
        validators=[validate_file_extension_pdf],
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = ["plik"]

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Plik załącznika",
                "plik",
            ),
        )
        super().__init__(*args, **kw)

    def clean_plik(self):
        if self.cleaned_data["plik"] is None:
            raise ValidationError(
                "Kliknij przycisk 'Przeglądaj' aby uzupełnić plik PDF z pełnym tekstem "
                "zgłaszanej publikacji. "
            )
        return self.cleaned_data["plik"]


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
            url="bpp:dyscyplina-naukowa-przypisanie-autocomplete",
            forward=["autor", "rok"],
        ),
        required=False,
    )

    rok = forms.IntegerField(widget=HiddenInput)

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
    # min_num=1,
    validate_min=True,
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
