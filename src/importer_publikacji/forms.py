from dal import autocomplete
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from bpp.const import GR_WPROWADZANIE_DANYCH, TO_AUTOR, TO_REDAKTOR
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Rodzaj_Prawa_Patentowego,
    Typ_KBN,
    Wydawca,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from pbn_api.models import Publication as PBNPublication

from .models import ImportSession
from .providers import (
    get_available_providers,
    get_providers_metadata,
)

User = get_user_model()


def _importer_users_queryset():
    """Użytkownicy z uprawnieniami do importera:
    superuserzy + członkowie grupy GR_WPROWADZANIE_DANYCH."""
    return User.objects.filter(
        Q(is_superuser=True) | Q(groups__name=GR_WPROWADZANIE_DANYCH)
    ).distinct()


class FetchForm(forms.Form):
    """Formularz pobierania danych od dostawcy."""

    provider = forms.ChoiceField(
        label="Źródło danych",
        choices=[],
        widget=forms.RadioSelect,
    )
    identifier = forms.CharField(
        label="Identyfikator",
        max_length=255,
        required=False,
    )
    text_input = forms.CharField(
        label="Dane publikacji",
        widget=forms.Textarea(attrs={"rows": 12, "cols": 80}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        last_provider = kwargs.pop("last_provider", None)
        super().__init__(*args, **kwargs)
        providers = get_available_providers()
        self.providers_metadata = get_providers_metadata()
        self.fields["provider"].choices = [
            (p, self.providers_metadata.get(p, {}).get("choice_label", p))
            for p in providers
        ]
        if last_provider and last_provider in providers:
            self.fields["provider"].initial = last_provider
        elif providers:
            self.fields["provider"].initial = providers[0]

    def clean(self):
        cleaned = super().clean()
        provider_name = cleaned.get("provider")
        if not provider_name:
            return cleaned

        meta = self.providers_metadata.get(provider_name, {})
        mode = meta.get("input_mode", "identifier")

        if mode == "text":
            if not cleaned.get("text_input", "").strip():
                self.add_error(
                    "text_input",
                    "To pole jest wymagane.",
                )
        else:
            if not cleaned.get("identifier", "").strip():
                self.add_error(
                    "identifier",
                    "To pole jest wymagane.",
                )

        return cleaned


class VerifyForm(forms.Form):
    """Formularz weryfikacji typu publikacji.

    Trój-drożny wybór ``rodzaj_rekordu`` (ciągłe/zwarte/patent) zastępuje dawny
    boolean ``jest_wydawnictwem_zwartym`` w UI — widok wylicza boolean z radia
    (back-compat downstream). Dla patentu (``bpp.Patent``) pola
    ``charakter_formalny``/``typ_kbn``/``jezyk`` są bezsensowne (model je
    hardkoduje / nie ma ``typ_kbn``), więc są warunkowo wymagane tylko dla
    ciągłego/zwartego (``clean()``); zamiast nich pokazujemy pola patentowe.
    """

    RODZAJ_CHOICES = [
        (ImportSession.RodzajRekordu.CIAGLE, "Wydawnictwo ciągłe (artykuł)"),
        (
            ImportSession.RodzajRekordu.ZWARTE,
            "Wydawnictwo zwarte (książka/rozdział)",
        ),
        (ImportSession.RodzajRekordu.PATENT, "Patent"),
    ]

    rodzaj_rekordu = forms.ChoiceField(
        label="Rodzaj rekordu",
        choices=RODZAJ_CHOICES,
        widget=forms.RadioSelect,
        required=True,
    )

    # Wyklucz D/H/PAT (praca doktorska/habilitacyjna/patent): mają własne
    # modele (Praca_Doktorska/Praca_Habilitacyjna/Patent) niedziedziczące po
    # Wydawnictwo_Ciagle/Zwarte, a fixture ma je ``ukryty=False`` — bez tego
    # wykluczenia operator mógł wybrać "Patent" tutaj i dostać zmieszany,
    # utknięty rekord (importer tworzy przez .objects.create(), więc
    # ZapobiegajNiewlasciwymCharakterom.clean_fields() — wołane tylko z
    # full_clean() — nigdy się nie odpala). Patenty mają teraz własną
    # ścieżkę (ImportSession.rodzaj_rekordu == PATENT → _create_patent).
    #
    # ``required=False`` na charakter/typ/jezyk — wymagalność egzekwuje
    # ``clean()`` warunkowo (wymagane tylko gdy rodzaj != PATENT).
    charakter_formalny = forms.ModelChoiceField(
        queryset=Charakter_Formalny.objects.filter(ukryty=False).exclude(
            skrot__in=["D", "H", "PAT"]
        ),
        label="Charakter formalny",
        required=False,
    )
    typ_kbn = forms.ModelChoiceField(
        queryset=Typ_KBN.objects.filter(ukryty=False),
        label="Typ MNiSW",
        required=False,
    )
    jezyk = forms.ModelChoiceField(
        queryset=Jezyk.objects.filter(widoczny=True),
        label="Język",
        required=False,
    )
    rok = forms.IntegerField(
        label="Rok publikacji",
        required=True,
        min_value=1900,
        max_value=2100,
        help_text=(
            "Uzupełniony automatycznie ze źródła — popraw, jeśli błędny "
            "lub brakuje (np. rekordy CrossRef bez roku wydania)."
        ),
    )

    # --- Pola patentowe (widoczne/istotne tylko gdy rodzaj_rekordu == PATENT).
    # Wszystkie required=False — model Patent dopuszcza null poza tytułem/rokiem.
    # Zwykłe widżety (bez select2): cały krok Verify używa gołych <select>,
    # a Jednostka/Rodzaj_Prawa_Patentowego to listy ograniczone.
    numer_zgloszenia = forms.CharField(
        label="Numer zgłoszenia",
        max_length=255,
        required=False,
    )
    data_zgloszenia = forms.DateField(
        label="Data zgłoszenia",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    numer_prawa_wylacznego = forms.CharField(
        label="Numer prawa wyłącznego",
        max_length=255,
        required=False,
    )
    data_decyzji = forms.DateField(
        label="Data decyzji",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    rodzaj_prawa = forms.ModelChoiceField(
        queryset=Rodzaj_Prawa_Patentowego.objects.all(),
        label="Rodzaj prawa",
        required=False,
    )
    uprawniony = forms.CharField(
        label="Uprawniony",
        max_length=512,
        required=False,
        help_text="Podmiot uprawniony z patentu (zapisywany w informacjach).",
    )
    wdrozenie = forms.NullBooleanField(
        label="Wdrożenie",
        required=False,
        widget=forms.NullBooleanSelect,
    )
    wydzial = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        label="Wydział / jednostka",
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        rodzaj = cleaned.get("rodzaj_rekordu")
        # Dla ciągłego/zwartego charakter/typ/jezyk są wymagane (jak dawniej);
        # dla patentu nie — Patent je hardkoduje / nie ma typ_kbn.
        if rodzaj and rodzaj != ImportSession.RodzajRekordu.PATENT:
            for pole in ("charakter_formalny", "typ_kbn", "jezyk"):
                if not cleaned.get(pole):
                    self.add_error(pole, "To pole jest wymagane.")
        return cleaned


class SourceForm(forms.Form):
    """Formularz dopasowania źródła."""

    zrodlo = forms.ModelChoiceField(
        queryset=Zrodlo.objects.all(),
        label="Źródło (czasopismo)",
        required=False,
        help_text="Wybierz istniejące źródło lub pozostaw puste",
        widget=autocomplete.ModelSelect2(
            url="bpp:admin-zrodlo-autocomplete",
        ),
    )
    wydawca = forms.ModelChoiceField(
        queryset=Wydawca.objects.all(),
        label="Wydawca",
        required=False,
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawca-autocomplete",
        ),
    )
    wydawca_opis = forms.CharField(
        label="Wydawca - szczegóły",
        max_length=256,
        required=False,
    )
    wydawnictwo_nadrzedne = forms.ModelChoiceField(
        queryset=Wydawnictwo_Zwarte.objects.all(),
        label="Wydawnictwo nadrzędne",
        required=False,
    )
    wydawnictwo_nadrzedne_w_pbn = forms.ModelChoiceField(
        queryset=PBNPublication.objects.all(),
        label="Wydawnictwo nadrzędne w PBN",
        required=False,
    )


class PunktacjaForm(forms.Form):
    """Formularz kroku punktacji — jedno pole, edytowalne."""

    punkty_kbn = forms.DecimalField(
        label="Punkty MNiSW",
        required=False,
        min_value=0,
    )


class AuthorMatchForm(forms.Form):
    """Formularz dopasowania pojedynczego autora."""

    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        label="Autor w BPP",
        required=False,
    )
    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        label="Jednostka",
        required=False,
    )
    dyscyplina = forms.ModelChoiceField(
        queryset=Dyscyplina_Naukowa.objects.all(),
        label="Dyscyplina",
        required=False,
    )
    zapisany_jako = forms.CharField(
        label="Zapisany jako",
        max_length=512,
        required=False,
    )
    typ = forms.TypedChoiceField(
        label="Typ autora",
        choices=[
            (TO_AUTOR, "autor"),
            (TO_REDAKTOR, "redaktor"),
        ],
        coerce=int,
        empty_value=None,
        required=False,
    )


class SessionFilterForm(forms.Form):
    """Formularz filtrowania listy sesji importu."""

    date_from = forms.DateField(
        label="Data od",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Data do",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    title = forms.CharField(
        label="Tytuł",
        required=False,
    )
    doi = forms.CharField(
        label="DOI",
        required=False,
    )
    provider_name = forms.ChoiceField(
        label="Źródło",
        required=False,
        choices=[],
    )
    created_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Utworzył",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "importer-user-select2",
            }
        ),
    )
    modified_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Zmodyfikował",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "importer-user-select2",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        users_qs = _importer_users_queryset()
        self.fields["created_by"].queryset = users_qs
        self.fields["modified_by"].queryset = users_qs

        providers = get_available_providers()
        self.fields["provider_name"].choices = [
            ("", "---------"),
        ] + [(p, p) for p in providers]
