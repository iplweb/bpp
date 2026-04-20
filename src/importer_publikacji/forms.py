from dal import autocomplete
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Typ_KBN,
    Wydawca,
    Zrodlo,
)

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
    """Formularz pobierania danych z dostawcy."""

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
        self.fields["provider"].choices = [(p, p) for p in providers]
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
    """Formularz weryfikacji typu publikacji."""

    charakter_formalny = forms.ModelChoiceField(
        queryset=Charakter_Formalny.objects.all(),
        label="Charakter formalny",
        required=True,
    )
    typ_kbn = forms.ModelChoiceField(
        queryset=Typ_KBN.objects.all(),
        label="Typ MNiSW",
        required=True,
    )
    jezyk = forms.ModelChoiceField(
        queryset=Jezyk.objects.filter(widoczny=True),
        label="Język",
        required=True,
    )
    jest_wydawnictwem_zwartym = forms.BooleanField(
        label="Wydawnictwo zwarte (książka/rozdział)",
        required=False,
    )


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
