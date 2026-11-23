import logging
import os
import tempfile

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.views.decorators.debug import sensitive_variables

from bpp.util import (
    formdefaults_html_after,
    formdefaults_html_before,
    zaloguj_polkniety_wyjatek,
)
from import_common.exceptions import (
    NiebezpiecznyPlikException,
    NieprawidloweHasloDoPlikuException,
)
from import_common.util import (
    INSTRUKCJA_USUNIECIA_HASLA,
    HasloDoPliku,
    czy_plik_zaszyfrowany,
    odszyfruj_plik,
    sprawdz_plik_importu,
    sprawdz_rozmiar_pliku,
)
from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon
from import_polon.utils import (
    PREFIKS_KATALOGU_TYMCZASOWEGO,
    read_excel_or_csv_dataframe_guess_encoding,
    usun_stare_katalogi_tymczasowe,
)

logger = logging.getLogger(__name__)


def validate_polon_headers(file_path):
    """
    Validate that the Excel/CSV file contains required headers for POLON import.
    Returns list of missing headers.
    """
    try:
        # Read only the header row to validate - use nrows=0 to read just headers
        data = read_excel_or_csv_dataframe_guess_encoding(file_path, nrows=0)

        # Check if we have any columns (headers)
        # data.empty will be True with nrows=0 even if headers exist
        if len(data.columns) == 0:
            return [
                "Nie można odczytać nagłówków z pliku "
                "- plik może być pusty lub uszkodzony"
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

    except NiebezpiecznyPlikException as e:
        # Plik za duży / bomba dekompresyjna / zabezpieczony hasłem — błąd
        # użytkownika z gotowym komunikatem, nie zgłaszamy do monitoringu.
        return [str(e)]
    except Exception as e:
        zaloguj_polkniety_wyjatek(
            f"Walidacja nagłówków pliku importu POLON (file_path={file_path!r})",
            logger=logger,
        )
        return [f"Błąd podczas odczytu nagłówków: {str(e)}"]


def validate_absencje_headers(file_path):
    """
    Validate that the Excel/CSV file contains required headers for absences import.
    Returns list of missing headers.
    """
    try:
        # Read only the header row to validate - use nrows=0 to read just headers
        data = read_excel_or_csv_dataframe_guess_encoding(file_path, nrows=0)

        # Check if we have any columns (headers)
        # data.empty will be True with nrows=0 even if headers exist
        if len(data.columns) == 0:
            return [
                "Nie można odczytać nagłówków z pliku "
                "- plik może być pusty lub uszkodzony"
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

    except NiebezpiecznyPlikException as e:
        # Plik za duży / bomba dekompresyjna / zabezpieczony hasłem — błąd
        # użytkownika z gotowym komunikatem, nie zgłaszamy do monitoringu.
        return [str(e)]
    except Exception as e:
        zaloguj_polkniety_wyjatek(
            f"Walidacja nagłówków pliku importu absencji (file_path={file_path!r})",
            logger=logger,
        )
        return [f"Błąd podczas odczytu nagłówków: {str(e)}"]


ROZSZERZENIA_PLIKU_IMPORTU = [".xlsx", ".xls", ".csv"]

KOMUNIKAT_PLIK_Z_HASLEM_FORMULARZ = (
    "Plik jest zabezpieczony hasłem. Wpisz hasło w polu „Hasło do pliku” albo "
    + INSTRUKCJA_USUNIECIA_HASLA
)


def _sprawdz_rozszerzenie(plik):
    """Odrzuca plik o rozszerzeniu innym niż .xlsx/.xls/.csv. Zwraca
    rozszerzenie (małymi literami)."""
    file_extension = os.path.splitext(plik.name)[1].lower()
    if file_extension not in ROZSZERZENIA_PLIKU_IMPORTU:
        raise ValidationError(
            "Niewłaściwy format pliku. "
            "Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv). "
            f"Otrzymano plik z rozszerzeniem: {file_extension}"
        )
    return file_extension


def _komunikat_brakujacych_naglowkow(missing_headers):
    error_msg = "Plik nie zawiera wymaganych nagłówków. Brakujące nagłówki:\n"
    error_msg += "\n".join(f"- {header}" for header in missing_headers)
    error_msg += "\n\nProszę upewnić się, że plik zawiera wszystkie wymagane kolumny."
    return error_msg


@sensitive_variables("haslo")
def przygotuj_plik_importu(plik, haslo, waliduj_naglowki):
    """Wspólna walidacja pliku dla importu POLON i absencji.

    Zapisuje upload do pliku tymczasowego, rozpoznaje plik Excel zabezpieczony
    hasłem i — gdy podano poprawne ``haslo`` — PODMIENIA go na odszyfrowaną
    kopię o tej samej nazwie. Dzięki temu do ``FileField`` (a więc i do
    zadania w tle, które czyta plik z dysku) trafia plik już bez hasła.
    Na koniec sprawdza nagłówki funkcją ``waliduj_naglowki(sciezka)``.

    Zwraca krotkę ``(plik, byl_zaszyfrowany)`` — plik do zapisania w modelu
    (oryginalny albo odszyfrowany) i informację, czy był zabezpieczony hasłem
    (wtedy jego kopię kasujemy z serwera po przetworzeniu).

    Hasło nie trafia do żadnego komunikatu, logu ani zgłoszenia błędu: ta
    funkcja go nie loguje, a ``odszyfruj_plik`` nie wkleja go do wyjątków.
    """
    file_extension = _sprawdz_rozszerzenie(plik)
    byl_zaszyfrowany = False

    # Nazwany plik na dysku jest potrzebny: ``sprawdz_plik_importu`` i odczyt
    # nagłówków (pandas) działają na ścieżce i wybierają parser po
    # rozszerzeniu. Katalog tymczasowy sprząta context manager — także przy
    # wyjątku — razem z oryginałem i odszyfrowaną kopią.
    # Katalogi osierocone przez zabity proces (SIGKILL/OOM pomija sprzątanie
    # context managera) kasujemy przy kolejnym imporcie — w TYM procesie/
    # kontenerze, bo /tmp nie jest współdzielony z workerem Celery.
    usun_stare_katalogi_tymczasowe()

    with tempfile.TemporaryDirectory(
        prefix=PREFIKS_KATALOGU_TYMCZASOWEGO, dir=tempfile.gettempdir()
    ) as katalog:
        tmp_file_path = os.path.join(katalog, "plik" + file_extension)
        with open(tmp_file_path, "wb") as tmp:
            for chunk in plik.chunks():
                tmp.write(chunk)

        try:
            # Ogólny limit rozmiaru PRZED czymkolwiek innym (także przed
            # rozpoznawaniem szyfrowania), potem rozpoznanie pliku z hasłem —
            # uszkodzony plik z hasłem daje tu komunikat, nie 500.
            sprawdz_rozmiar_pliku(tmp_file_path)
            zaszyfrowany = czy_plik_zaszyfrowany(tmp_file_path)
        except NiebezpiecznyPlikException as e:
            raise ValidationError(str(e)) from None

        if zaszyfrowany:
            if not haslo:
                raise ValidationError(KOMUNIKAT_PLIK_Z_HASLEM_FORMULARZ)

            try:
                # ``odszyfruj_plik`` sam pilnuje (niższego) limitu rozmiaru
                # pliku z hasłem; odszyfrowana kopia przejdzie niżej przez
                # pełne ``sprawdz_plik_importu`` (rozmiar + bomba dekompresji).
                odszyfrowany = odszyfruj_plik(tmp_file_path, haslo)
            except NieprawidloweHasloDoPlikuException as e:
                raise ValidationError(str(e)) from None
            except NiebezpiecznyPlikException as e:
                raise ValidationError(str(e)) from None

            with open(tmp_file_path, "wb") as f:
                f.write(odszyfrowany)

            plik = SimpleUploadedFile(
                plik.name,
                odszyfrowany,
                content_type=getattr(plik, "content_type", None),
            )
            byl_zaszyfrowany = True
        # Hasło do niezaszyfrowanego pliku po prostu ignorujemy.

        # Limity (rozmiar, bomba dekompresji, hasło) sprawdzamy tu jawnie —
        # także dla odszyfrowanej kopii — żeby komunikat nie trafił do listy
        # „brakujących nagłówków".
        try:
            sprawdz_plik_importu(tmp_file_path)
        except NiebezpiecznyPlikException as e:
            raise ValidationError(str(e)) from None

        missing_headers = waliduj_naglowki(tmp_file_path)
        if missing_headers:
            raise ValidationError(_komunikat_brakujacych_naglowkow(missing_headers))

    return plik, byl_zaszyfrowany


class PoleHaslaDoPliku(forms.CharField):
    """``CharField``, którego ``cleaned_data`` to ``HasloDoPliku`` — obiekt
    nieujawniający wartości w ``repr`` (tracebacki w monitoringu błędów)."""

    def clean(self, value):
        return HasloDoPliku(super().clean(value))


def pole_hasla_do_pliku():
    """Opcjonalne pole na hasło do zaszyfrowanego pliku Excel. NIE jest
    polem modelu — hasło żyje tylko w czasie walidacji formularza."""
    return PoleHaslaDoPliku(
        label="Hasło do pliku",
        required=False,
        strip=False,
        help_text=(
            "Tylko jeśli plik Excel jest zabezpieczony hasłem. Hasło służy "
            "wyłącznie do odszyfrowania pliku — nie jest nigdzie zapisywane."
        ),
        widget=forms.PasswordInput(
            render_value=False,
            # „new-password" — inaczej przeglądarka wpisze tu z pamięci hasło
            # logowania do BPP i potraktujemy je jako hasło do pliku.
            attrs={"autocomplete": "new-password"},
        ),
    )


class NowyImportAbsencjiForm(forms.ModelForm):
    haslo_do_pliku = pole_hasla_do_pliku()

    # Hasło musi być w ``cleaned_data``, zanim ``clean_plik`` otworzy plik.
    field_order = ["haslo_do_pliku"]

    class Meta:
        model = ImportPlikuAbsencji
        fields = ["plik", "zapisz_zmiany_do_bazy"]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # ``haslo_do_pliku`` jest czyszczone PRZED ``plik`` (``field_order``).
            plik, byl_zaszyfrowany = przygotuj_plik_importu(
                plik,
                self.cleaned_data.get("haslo_do_pliku") or HasloDoPliku(),
                validate_absencje_headers,
            )
            # Po przetworzeniu odszyfrowana kopia zostanie usunięta z serwera.
            self.instance.plik_byl_zaszyfrowany = byl_zaszyfrowany
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
                    Column("haslo_do_pliku", css_class="large-12 small-12"),
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
    )
    dyscyplina = forms.ChoiceField(
        required=False,
        label="Dyscyplina",
        choices=[("", "---------")],
    )
    grupa_stanowisk = forms.ChoiceField(
        required=False,
        label="Grupa stanowiska",
        choices=[("", "---------")],
    )
    pokaz_tylko_roznice = forms.BooleanField(
        required=False,
        label="Pokaż tylko różnice",
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
    haslo_do_pliku = pole_hasla_do_pliku()

    # Hasło musi być w ``cleaned_data``, zanim ``clean_plik`` otworzy plik.
    field_order = ["haslo_do_pliku"]

    class Meta:
        model = ImportPlikuPolon
        fields = [
            "plik",
            "rok",
            "zapisz_zmiany_do_bazy",
            "ukryj_niezmatchowanych_autorow",
            "ignoruj_miejsce_pracy",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # ``haslo_do_pliku`` jest czyszczone PRZED ``plik`` (``field_order``).
            plik, byl_zaszyfrowany = przygotuj_plik_importu(
                plik,
                self.cleaned_data.get("haslo_do_pliku") or HasloDoPliku(),
                validate_polon_headers,
            )
            # Po przetworzeniu odszyfrowana kopia zostanie usunięta z serwera.
            self.instance.plik_byl_zaszyfrowany = byl_zaszyfrowany
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
                    Column("ignoruj_miejsce_pracy", css_class="large-12 small-12"),
                ),
                Row(
                    Column("zapisz_zmiany_do_bazy", css_class="large-12 small-12"),
                ),
                Row(
                    Column("plik", css_class="large-12 small-12"),
                ),
                Row(
                    Column("haslo_do_pliku", css_class="large-12 small-12"),
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
