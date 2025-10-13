import os
import tempfile

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

from bpp.util import formdefaults_html_after, formdefaults_html_before


def validate_polon_headers(file_path):
    """
    Validate that the Excel/CSV file contains required headers for POLON import.
    Returns list of missing headers.
    """
    try:
        # Read only the header row to validate - use nrows=0 to read just headers
        data = read_excel_or_csv_dataframe_guess_encoding(file_path, nrows=0)

        # Check if we have any columns (headers) - data.empty will be True with nrows=0 even if headers exist
        if len(data.columns) == 0:
            return [
                "Nie można odczytać nagłówków z pliku - plik może być pusty lub uszkodzony"
            ]

        actual_headers = set(data.columns.str.upper())

        # Required headers (case-insensitive comparison)
        required_headers = {
            "NAZWISKO",
            "IMIE",
            "ZATRUDNIENIE",
            "OSWIADCZENIE_N",
            "OSWIADCZENIE_O_DYSCYPLINACH",
            "ZATRUDNIENIE_OD",
            "ZATRUDNIENIE_DO",
            "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA",
            "PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA",
            "DYSCYPLINA_N",
            "DYSCYPLINA_N_KOLEJNA",
            "OSWIADCZONA_DYSCYPLINA_PIERWSZA",
            "OSWIADCZONA_DYSCYPLINA_DRUGA",
        }

        missing_headers = []
        for header in required_headers:
            if header not in actual_headers:
                missing_headers.append(header)

        return missing_headers

    except Exception as e:
        return [f"Błąd podczas odczytu nagłówków: {str(e)}"]


def validate_absencje_headers(file_path):
    """
    Validate that the Excel/CSV file contains required headers for absences import.
    Returns list of missing headers.
    """
    try:
        # Read only the header row to validate - use nrows=0 to read just headers
        data = read_excel_or_csv_dataframe_guess_encoding(file_path, nrows=0)

        # Check if we have any columns (headers) - data.empty will be True with nrows=0 even if headers exist
        if len(data.columns) == 0:
            return [
                "Nie można odczytać nagłówków z pliku - plik może być pusty lub uszkodzony"
            ]

        actual_headers = set(data.columns.str.upper())

        # Required headers (case-insensitive comparison)
        required_headers = {
            "NAZWISKO",
            "IMIE",
            "ROK_NIEOBECNOSC",
        }

        missing_headers = []
        for header in required_headers:
            if header not in actual_headers:
                missing_headers.append(header)

        return missing_headers

    except Exception as e:
        return [f"Błąd podczas odczytu nagłówków: {str(e)}"]


class NowyImportAbsencjiForm(forms.ModelForm):
    class Meta:
        model = ImportPlikuAbsencji
        fields = ["plik", "zapisz_zmiany_do_bazy"]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # Check file extension
            file_extension = os.path.splitext(plik.name)[1].lower()
            valid_extensions = [".xlsx", ".xls", ".csv"]

            if file_extension not in valid_extensions:
                raise ValidationError(
                    f"Niewłaściwy format pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv). "
                    f"Otrzymano plik z rozszerzeniem: {file_extension}"
                )

            # Check MIME type if available
            if hasattr(plik, "content_type"):
                valid_mime_types = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
                    "application/vnd.ms-excel",  # xls
                    "text/csv",  # csv
                    "application/csv",  # csv alternative
                    "application/octet-stream",  # sometimes files are detected as this
                ]
                if plik.content_type not in valid_mime_types:
                    # Don't reject based on MIME type alone if extension is valid
                    # Some browsers may report incorrect MIME types
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            "Niewłaściwy typ pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
                        )

            # Validate headers for absences import
            # Save file temporarily to validate headers
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as tmp_file:
                for chunk in plik.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name

            try:
                missing_headers = validate_absencje_headers(tmp_file_path)
                if missing_headers:
                    error_msg = (
                        "Plik nie zawiera wymaganych nagłówków. Brakujące nagłówki:\n"
                    )
                    error_msg += "\n".join(f"- {header}" for header in missing_headers)
                    error_msg += "\n\nProszę upewnić się, że plik zawiera wszystkie wymagane kolumny."
                    raise ValidationError(error_msg)
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                except OSError:
                    pass

        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("plik", css_class="large-12 small-12"),
                ),
                Row(
                    Column("zapisz_zmiany_do_bazy", css_class="large-12 small-12"),
                ),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)


class WierszImportuPlikuPolonFilterForm(forms.Form):
    autor_wiersz = forms.CharField(
        required=False,
        label="Autor / Wiersz",
        help_text="Tekst: szukaj autorze lub rezultacie. Liczba: numer wiersza",
    )
    dyscyplina = forms.ChoiceField(
        required=False,
        label="Dyscyplina",
        choices=[("", "---------")],
        help_text="Szukaj w dyscyplinie lub subdyscyplinie",
    )
    grupa_stanowisk = forms.ChoiceField(
        required=False,
        label="Grupa stanowiska",
        choices=[("", "---------")],
        help_text="Filtruj po grupie stanowiska",
    )

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop("queryset", None)
        super().__init__(*args, **kwargs)

        if queryset is not None:
            # Get unique disciplines from both dyscyplina and subdyscyplina fields
            dyscypliny = set()

            # Add disciplines
            dyscypliny.update(
                queryset.exclude(dane_z_xls__DYSCYPLINA_N__isnull=True)
                .exclude(dane_z_xls__DYSCYPLINA_N="")
                .values_list("dane_z_xls__DYSCYPLINA_N", flat=True)
                .distinct()
            )

            # Add subdisciplines
            dyscypliny.update(
                queryset.exclude(dane_z_xls__DYSCYPLINA_N_KOLEJNA__isnull=True)
                .exclude(dane_z_xls__DYSCYPLINA_N_KOLEJNA="")
                .values_list("dane_z_xls__DYSCYPLINA_N_KOLEJNA", flat=True)
                .distinct()
            )

            # Remove empty values and sort
            dyscypliny = sorted([d for d in dyscypliny if d])

            self.fields["dyscyplina"].choices = [("", "---------")] + [
                (d, d) for d in dyscypliny
            ]

            # Get unique GRUPA_STANOWISK values
            grupy_stanowisk = list(
                queryset.exclude(dane_z_xls__GRUPA_STANOWISK__isnull=True)
                .exclude(dane_z_xls__GRUPA_STANOWISK="")
                .values_list("dane_z_xls__GRUPA_STANOWISK", flat=True)
                .distinct()
                .order_by("dane_z_xls__GRUPA_STANOWISK")
            )

            self.fields["grupa_stanowisk"].choices = [("", "---------")] + [
                (gs, gs) for gs in grupy_stanowisk
            ]

    def clean_autor_wiersz(self):
        value = self.cleaned_data.get("autor_wiersz")
        if value:
            value = value.strip()
            try:
                return int(value)
            except ValueError:
                return value
        return value


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPlikuPolon
        fields = [
            "plik",
            "rok",
            "zapisz_zmiany_do_bazy",
            "ukryj_niezmatchowanych_autorow",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # Check file extension
            file_extension = os.path.splitext(plik.name)[1].lower()
            valid_extensions = [".xlsx", ".xls", ".csv"]

            if file_extension not in valid_extensions:
                raise ValidationError(
                    f"Niewłaściwy format pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv). "
                    f"Otrzymano plik z rozszerzeniem: {file_extension}"
                )

            # Check MIME type if available
            if hasattr(plik, "content_type"):
                valid_mime_types = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
                    "application/vnd.ms-excel",  # xls
                    "text/csv",  # csv
                    "application/csv",  # csv alternative
                    "application/octet-stream",  # sometimes files are detected as this
                ]
                if plik.content_type not in valid_mime_types:
                    # Don't reject based on MIME type alone if extension is valid
                    # Some browsers may report incorrect MIME types
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            "Niewłaściwy typ pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
                        )

            # Validate headers for POLON import
            # Save file temporarily to validate headers
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as tmp_file:
                for chunk in plik.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name

            try:
                missing_headers = validate_polon_headers(tmp_file_path)
                if missing_headers:
                    error_msg = (
                        "Plik nie zawiera wymaganych nagłówków. Brakujące nagłówki:\n"
                    )
                    error_msg += "\n".join(f"- {header}" for header in missing_headers)
                    error_msg += "\n\nProszę upewnić się, że plik zawiera wszystkie wymagane kolumny."
                    raise ValidationError(error_msg)
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                except OSError:
                    pass

        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("rok", css_class="large-12 small-12"),
                ),
                Row(
                    Column(
                        "ukryj_niezmatchowanych_autorow", css_class="large-12 small-12"
                    ),
                ),
                Row(
                    Column("zapisz_zmiany_do_bazy", css_class="large-12 small-12"),
                ),
                Row(
                    Column("plik", css_class="large-12 small-12"),
                ),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)
