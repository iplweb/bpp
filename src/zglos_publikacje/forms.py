from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Fieldset, Layout
from dal import autocomplete
from dal_select2_queryset_sequence.widgets import (
    QuerySetSequenceSelect2,
)
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.widgets import HiddenInput

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka, Uczelnia
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
)
from zglos_publikacje.validators import validate_file_extension_pdf


class MultipleFileInput(forms.FileInput):
    """Widget umożliwiający upload wielu plików."""

    allow_multiple_selected = True

    def __init__(self, attrs=None):
        default_attrs = {"accept": ".pdf"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class TolerantQuerySetSequenceSelect2(QuerySetSequenceSelect2):
    """QSS widget odporny na zniekształcone wartości w `selected_choices`.

    Bazowy `dal_queryset_sequence.widgets.QuerySetSequenceSelectMixin
    .filter_choices_to_render` rozpakowuje
    `ctype_pk, model_pk = choice.split('-', 1)` bez wcześniejszego
    sprawdzenia formatu. Jeśli POST przyniesie wartość bez `-`
    (np. user wpisał coś w autocomplete i nie wybrał z dropdowna),
    rozpakowanie wybucha `ValueError` i cały render template-u
    crashuje z HTTP 500.

    Pre-filtrujemy `selected_choices` do wartości w formacie
    `<ctype_pk>-<pk>` przed delegacją do super().
    """

    def filter_choices_to_render(self, selected_choices):
        valid = [c for c in selected_choices if c and "-" in str(c)]
        super().filter_choices_to_render(valid)


class MultipleFileField(forms.FileField):
    """FileField obsługujący listę plików z MultipleFileInput.

    Bez tej klasy zwykły `forms.FileField` przy pojedynczym pliku
    otrzymanym z widgeta multi-select dostaje `[UploadedFile]` i
    próbuje `.name` na liście → `ValidationError('invalid')` z
    komunikatem „No file was submitted. Check the encoding type...".
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


# Mapowanie wartości formularza na enum Rodzaje
RODZAJ_FORM_TO_MODEL = {
    "ARTYKUL": Zgloszenie_Publikacji.Rodzaje.ARTYKUL,
    "MONOGRAFIA": Zgloszenie_Publikacji.Rodzaje.MONOGRAFIA,
    "ROZDZIAL": Zgloszenie_Publikacji.Rodzaje.ROZDZIAL_W_MONOGRAFII,
    "POZOSTALE": Zgloszenie_Publikacji.Rodzaje.INNE,
}

FORMA_DOSTEPU_FORM_TO_MODEL = {
    "OTWARTY": Zgloszenie_Publikacji.FormyDostepu.OTWARTY,
    "OGRANICZONY": Zgloszenie_Publikacji.FormyDostepu.OGRANICZONY,
}


_PBN_PREFIX = (
    "Pole wymagane — system Polska Bibliografia Naukowa (PBN), do którego"
    " trafiają dane o publikacjach, wymaga podania adresu URL lub"
    " identyfikatora DOI."
)
_OA_TEKST = "Dla publikacji w otwartym dostępie prosimy o link do pełnego tekstu."
_OGR_INFO_TEKST = (
    "Dla publikacji z ograniczonym dostępem prosimy o podanie linku do strony"
    " z informacją o publikacji."
)
_OGR_KATALOGI_TEKST = (
    "Jeśli pełny tekst nie jest dostępny publicznie, wystarczy podać link do"
    " strony wydawcy, wpisu w katalogu Biblioteki Narodowej (bn.org.pl) lub"
    " katalogu NUKAT (nukat.edu.pl)."
)
_FULL_URL_TEKST = (
    "Prosimy o podanie pełnego adresu URL — z prefiksem"
    " https:// lub http:// na początku. Jeżeli posiadasz sam"
    " identyfikator DOI, dodaj go z prefiksem"
    " https://dx.doi.org/[numer DOI]."
)

# Mapowanie (rodzaj, forma_dostepu) → tekst pomocniczy pola `strona_www`.
STRONA_WWW_HELP_TEXT = {
    ("ARTYKUL", "OTWARTY"): f"{_PBN_PREFIX} {_OA_TEKST} {_FULL_URL_TEKST}",
    ("ARTYKUL", "OGRANICZONY"): f"{_PBN_PREFIX} {_OGR_INFO_TEKST} {_FULL_URL_TEKST}",
    ("MONOGRAFIA", "OTWARTY"): f"{_PBN_PREFIX} {_OA_TEKST} {_FULL_URL_TEKST}",
    ("MONOGRAFIA", "OGRANICZONY"): (
        f"{_PBN_PREFIX} {_OGR_KATALOGI_TEKST} {_FULL_URL_TEKST}"
    ),
    ("ROZDZIAL", "OTWARTY"): f"{_PBN_PREFIX} {_OA_TEKST} {_FULL_URL_TEKST}",
    ("ROZDZIAL", "OGRANICZONY"): (
        f"{_PBN_PREFIX} {_OGR_KATALOGI_TEKST} {_FULL_URL_TEKST}"
    ),
    ("POZOSTALE", "OTWARTY"): _FULL_URL_TEKST,
    ("POZOSTALE", "OGRANICZONY"): f"{_OGR_INFO_TEKST} {_FULL_URL_TEKST}",
}


class RodzajPublikacjiForm(forms.Form):
    """Krok 0: wybór rodzaju publikacji (kafelki)."""

    rodzaj = forms.ChoiceField(
        label="Rodzaj publikacji",
        choices=[
            ("ARTYKUL", "Artykuł"),
            ("MONOGRAFIA", "Książka / Monografia"),
            ("ROZDZIAL", "Rozdział"),
            ("POZOSTALE", "Inne"),
        ],
        widget=forms.RadioSelect,
    )


class FormaDostepuForm(forms.Form):
    """Krok 1: wybór formy dostępu (kafelki)."""

    forma_dostepu = forms.ChoiceField(
        label="Forma dostępu",
        choices=[
            ("OTWARTY", "Otwarty dostęp"),
            ("OGRANICZONY", "Dostęp ograniczony"),
        ],
        widget=forms.RadioSelect,
    )


class Zgloszenie_Publikacji_DaneForm(forms.ModelForm):
    """Krok 2: formularz danych o publikacji.

    Pola zależą od wyborów z kroków 0 (rodzaj) i 1 (forma
    dostępu). Dynamicznie dodaje/usuwa pola w __init__.
    """

    rok = forms.IntegerField(
        help_text=(
            "Rok publikacji zgłaszanej pracy. Rok na"
            " późniejszych etapach używany jest do ustalenia"
            " i zweryfikowania dyscyplin naukowych zgłoszonych"
            " przez autorów."
        ),
    )

    tytul_oryginalny = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "cols": 80}),
        help_text=(
            "Tytuł pracy. Prosimy o wpisanie samego tytułu."
            " Proszę nie wpisywać źródła, miejsca publikacji,"
            " autorów itp. -- wyłącznie tytuł pracy."
        ),
        max_length=300,
    )

    email = forms.EmailField(
        help_text=(
            "Prosimy o podanie poprawnego adresu e-mail."
            " W razie problemów ze zgłoszeniem na ten adres"
            " zostanie skierowana dalsza korespondencja."
        )
    )

    zgoda_na_publikacje_pelnego_tekstu = forms.ChoiceField(
        choices=[
            (None, "proszę określić"),
            (
                True,
                "tak, wyrażam zgodę na umieszczenie pełnego"
                " tekstu publikacji w repozytorium",
            ),
            (
                False,
                "nie, nie wyrażam zgody na umieszczenie"
                " pełnego tekstu publikacji w repozytorium",
            ),
        ],
        required=True,
    )

    strona_www = forms.URLField(
        label="Link do publikacji lub DOI",
        max_length=1024,
        required=True,
    )

    pliki = MultipleFileField(
        label="Pliki PDF",
        required=False,
        help_text=(
            "Pliki PDF z pełnym tekstem pracy. Wymagany"
            " min. 1 plik. Możliwość dodania wielu plików."
        ),
        validators=[validate_file_extension_pdf],
    )

    wydawnictwo_nadrzedne = forms.CharField(
        required=False,
        widget=TolerantQuerySetSequenceSelect2(
            url=("zglos_publikacje:public-wydawnictwo-nadrzedne-autocomplete"),
        ),
        label="Wydawnictwo nadrzędne",
        help_text=(
            "Wyszukaj monografię, w której jest rozdział."
            " Jeśli nie znaleziono -- wpisz tytuł ręcznie"
            " w polu poniżej."
        ),
    )

    wydawnictwo_nadrzedne_tekst = forms.CharField(
        label="Wydawnictwo nadrzędne (wpisz ręcznie)",
        max_length=512,
        required=False,
        help_text=(
            "Jeśli monografii nie znaleziono w wyszukiwarce, wpisz jej tytuł ręcznie."
        ),
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "tytul_oryginalny",
            "rok",
            "strona_www",
            "email",
            "zgoda_na_publikacje_pelnego_tekstu",
        ]

    def _usun_pola_wg_formy_dostepu(self, forma_dostepu):
        """Usuwa/modyfikuje pola zależne od formy dostępu."""
        if forma_dostepu == "OTWARTY":
            self.fields.pop("pliki", None)
        elif forma_dostepu == "OGRANICZONY":
            pass  # strona_www wymagana, pliki wymagane — nic nie zmieniamy
        else:
            self.fields.pop("pliki", None)

    def _dostosuj_strona_www(self, rodzaj, forma_dostepu):
        """Ustaw help_text i required dla `strona_www`.

        Treść pomocnicza zależy od kombinacji (rodzaj, forma dostępu) —
        dla publikacji typu „Inne" PBN nie wymaga linku, więc pole jest
        opcjonalne (przy ograniczonym dostępie wymagany pozostaje PDF).
        """
        field = self.fields["strona_www"]
        field.help_text = STRONA_WWW_HELP_TEXT.get((rodzaj, forma_dostepu), "")
        if rodzaj == "POZOSTALE":
            field.required = False

    def _usun_pola_wg_rodzaju(self, rodzaj):
        """Usuwa pola zależne od rodzaju publikacji."""
        if rodzaj == "MONOGRAFIA":
            self.fields.pop("wydawnictwo_nadrzedne", None)
            self.fields.pop("wydawnictwo_nadrzedne_tekst", None)
        elif rodzaj == "ROZDZIAL":
            pass  # wszystkie pola zostają
        else:
            # ARTYKUL, POZOSTALE -- brak wyd. nadrzędnego
            self.fields.pop("wydawnictwo_nadrzedne", None)
            self.fields.pop("wydawnictwo_nadrzedne_tekst", None)

    def _zbuduj_layout(self):
        """Buduje layout na podstawie aktualnych pól."""
        layout_fields = ["tytul_oryginalny", "rok", "email"]
        optional = [
            "zgoda_na_publikacje_pelnego_tekstu",
            "strona_www",
            "pliki",
            "wydawnictwo_nadrzedne",
            "wydawnictwo_nadrzedne_tekst",
        ]
        for name in optional:
            if name in self.fields:
                layout_fields.append(name)

        self.helper.layout = Layout(
            Fieldset("Dane o publikacji", *layout_fields),
        )

    def __init__(
        self, *args, rodzaj=None, forma_dostepu=None, pliki_juz_zapisane=False, **kw
    ):
        self.rodzaj = rodzaj
        self.forma_dostepu = forma_dostepu
        # Wizard zapisuje pliki kroku 2 poza storage formtools, więc przy
        # rewalidacji (render_done) `self.files` jest puste mimo że pliki
        # są. Ta flaga pozwala `clean()` zaakceptować taki przypadek.
        self.pliki_juz_zapisane = pliki_juz_zapisane

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "custom"
        self.helper.form_action = "."

        super().__init__(*args, **kw)

        uczelnia = Uczelnia.objects.get_default()
        if not uczelnia.pytaj_o_zgode_na_publikacje_pelnego_tekstu:
            self.fields.pop("zgoda_na_publikacje_pelnego_tekstu", None)

        self._usun_pola_wg_formy_dostepu(forma_dostepu)
        self._usun_pola_wg_rodzaju(rodzaj)
        self._dostosuj_strona_www(rodzaj, forma_dostepu)
        self._zbuduj_layout()

    def clean(self):
        cleaned = super().clean()

        # Dla rozdziału wymagane wyd. nadrzędne (FK lub tekst)
        if self.rodzaj == "ROZDZIAL":
            wn = cleaned.get("wydawnictwo_nadrzedne") or ""
            wn_tekst = cleaned.get("wydawnictwo_nadrzedne_tekst", "").strip()

            # Jeśli `wn` jest niepuste, ale nie ma formatu `<ct>-<pk>`,
            # znaczy user wpisał tytuł w autocomplete i nie wybrał z
            # dropdowna. Traktujemy to jako freetext (przenosimy do
            # `wn_tekst`), żeby:
            # 1) widget QSS nie wybuchał na re-renderze (`split('-', 1)`),
            # 2) `done()` zapisał wpisany tytuł zamiast cicho zgubić.
            if wn and "-" not in wn:
                if not wn_tekst:
                    wn_tekst = wn
                    cleaned["wydawnictwo_nadrzedne_tekst"] = wn_tekst
                cleaned["wydawnictwo_nadrzedne"] = ""
                wn = ""

            if not wn and not wn_tekst:
                raise ValidationError(
                    "Dla rozdziału wymagane jest podanie"
                    " wydawnictwa nadrzędnego -- wybierz"
                    " z wyszukiwarki lub wpisz ręcznie."
                )

        # Dla dostępu ograniczonego wymagany min. 1 plik
        if self.forma_dostepu == "OGRANICZONY":
            pliki_key = self.add_prefix("pliki")
            # W wizardze self.files może być dict lub QueryDict
            if hasattr(self.files, "getlist"):
                pliki = self.files.getlist(pliki_key)
            else:
                pliki = self.files.get(pliki_key, [])
                # Upewnij się, że mamy listę
                if pliki and not isinstance(pliki, list):
                    pliki = [pliki]
                elif not pliki:
                    pliki = []

            if not pliki and not self.pliki_juz_zapisane:
                raise ValidationError(
                    "Dla dostępu ograniczonego wymagany jest"
                    " przynajmniej jeden plik PDF."
                )

        return cleaned


class Zgloszenie_Publikacji_Plik(forms.ModelForm):
    """Legacy: formularz pliku (zachowany dla kompatybilności)."""

    plik = forms.FileField(
        required=False,
        help_text=(
            "Ponieważ w poprzednim formularzu nie podano"
            " adresu WWW ani adresu DOI publikacji, prosimy"
            " o załączenie pełnego tekstu pracy w formacie"
            " PDF. Dodawany plik wyłącznie na potrzeby"
            " zarejestrowania rekordu w bazie publikacji -"
            " do wglądu Biblioteki; nie będzie dalej"
            " udostępniany."
        ),
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
                "Kliknij przycisk 'Przeglądaj' aby uzupełnić"
                " plik PDF z pełnym tekstem zgłaszanej"
                " publikacji. "
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
                "rok",
            )
        )
        super().__init__(*args, **kw)


Zgloszenie_Publikacji_AutorFormSet = inlineformset_factory(
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    form=Zgloszenie_Publikacji_AutorForm,
    extra=1,
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
