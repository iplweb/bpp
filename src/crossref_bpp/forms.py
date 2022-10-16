import logging

from django import forms
from django.core.exceptions import ValidationError
from sentry_sdk import capture_exception

from crossref_bpp.models import CrossrefAPICache
from import_common.normalization import normalize_doi


class PobierzZCrossrefAPIForm(forms.Form):
    identyfikator_doi = forms.CharField(
        label="Identyfikator DOI",
        help_text="... może być również adres URL http://dx.doi.org/... lub http://doi.org/...",
        required=True,
        widget=forms.TextInput(attrs={"style": "width: 512px"}),
    )

    def clean_identyfikator_doi(self):
        v = self.cleaned_data["identyfikator_doi"]
        return normalize_doi(v)

    def clean(self):
        doi = self.cleaned_data["identyfikator_doi"]
        try:
            data = CrossrefAPICache.objects.get_by_doi(doi)
        except Exception as e:
            capture_exception(e)
            logging.exception(e)
            raise ValidationError(f"Podczas pobierania danych wystąpił błąd {e}")

        if data is None:
            raise ValidationError(
                f'Dla podanego DOI "{doi}" nie znaleziono nic po stronie CrossRef API'
            )

        self.cleaned_data["json_data"] = data
