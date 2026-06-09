import os
import sys

import rollbar
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import Http404
from django.shortcuts import render
from django.utils.datastructures import MultiValueDict
from django.views.generic import TemplateView
from formtools.wizard.views import SessionWizardView
from messages_extends import messages
from templated_email import send_templated_mail

from bpp.const import PUSTY_ADRES_EMAIL, TO_AUTOR
from bpp.core import zgloszenia_publikacji_emails
from bpp.models import Typ_Odpowiedzialnosci, Uczelnia
from bpp.models.wydawca import Wydawca
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.views.mixins import UczelniaSettingRequiredMixin
from import_common.normalization import normalize_tytul_publikacji
from pbn_api.models.publication import (
    Publication as PBN_Publication,
)
from pbn_api.models.publisher import Publisher as PBN_Publisher
from zglos_publikacje import const
from zglos_publikacje.forms import (
    FORMA_DOSTEPU_FORM_TO_MODEL,
    RODZAJ_FORM_TO_MODEL,
    FormaDostepuForm,
    RodzajPublikacjiForm,
    Zgloszenie_Publikacji_AutorFormSet,
    Zgloszenie_Publikacji_DaneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
)
from zglos_publikacje.models import (
    Obslugujacy_Zgloszenia_Wydzialow,
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Zalacznik,
    skroc_nazwe_pliku,
)


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"


def pokazuj_formularz_platnosci(wizard):
    """Pokaż formularz opłat jeśli uczelnia wymaga tego
    dla wybranego rodzaju publikacji."""
    uczelnia = Uczelnia.objects.get_for_request(wizard.request)
    if uczelnia is None:
        return False

    cleaned = wizard.get_cleaned_data_for_step("0") or {}
    rodzaj = cleaned.get("rodzaj")
    if not rodzaj:
        return False

    mapping = {
        "ARTYKUL": uczelnia.wymagaj_oplatach_artykul,
        "MONOGRAFIA": uczelnia.wymagaj_oplatach_monografia,
        "ROZDZIAL": uczelnia.wymagaj_oplatach_rozdzial,
        "POZOSTALE": uczelnia.wymagaj_oplatach_inne,
    }
    return mapping.get(rodzaj, False)


def _resolve_qss_value(value_str):
    """Rozwiąż wartość z QuerySetSequenceSelect2.

    Format wartości: "content_type_id-pk"
    Zwraca tuple (model_instance, content_type) lub (None, None).
    """
    if not value_str or not isinstance(value_str, str):
        return None, None

    parts = value_str.split("-", 1)
    if len(parts) != 2:
        return None, None

    try:
        ct_id = int(parts[0])
        pk = parts[1]
    except (ValueError, TypeError):
        return None, None

    try:
        ct = ContentType.objects.get(pk=ct_id)
        model_class = ct.model_class()
        if model_class is None:
            return None, None
        instance = model_class.objects.get(pk=pk)
        return instance, ct
    except (ContentType.DoesNotExist, Exception):
        return None, None


def _process_autorzy_formset(
    autorzy_formset, publication_object, typ_odpowiedzialnosci
):
    """Process the authors formset and save author records."""
    if not autorzy_formset.is_valid():
        return

    for no, form in enumerate(autorzy_formset):
        if not form.is_valid():
            continue

        if form.cleaned_data.get("DELETE"):
            if form.instance.pk:
                form.instance.delete()
            continue

        if not form.cleaned_data:
            continue

        instance = form.save(commit=False)
        instance.rekord = publication_object
        instance.kolejnosc = no
        instance.typ_odpowiedzialnosci = typ_odpowiedzialnosci
        instance.save()


def _send_notification_email(publication_object, request):
    """Send notification email about new publication submission."""
    recipient_list = None

    jednostka_do_powiadomienia = None

    for zpa in publication_object.zgloszenie_publikacji_autor_set.all().select_related(
        "jednostka"
    ):
        if zpa.jednostka_id is not None:
            jednostka_do_powiadomienia = zpa.jednostka

        if jednostka_do_powiadomienia.skupia_pracownikow:
            break

    if jednostka_do_powiadomienia is not None:
        recipient_list = Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_wydzialu(
            jednostka_do_powiadomienia.wydzial
        )

    if not recipient_list:
        recipient_list = zgloszenia_publikacji_emails()

    try:
        send_templated_mail(
            template_name="nowe_zgloszenie",
            from_email=getattr(
                settings,
                "DEFAULT_FROM_EMAIL",
                "webmaster@localhost",
            ),
            headers={"reply-to": publication_object.email},
            recipient_list=recipient_list,
            context={
                "object": publication_object,
                "site_url": request.get_host(),
            },
        )
    except Exception:
        rollbar.report_exc_info(sys.exc_info())

        messages.add_message(
            request,
            messages.WARNING,
            "Z uwagi na błąd wysyłania komunikatu"
            " z powiadomieniem, zespół Biblioteki nie"
            " został powiadomiony o dodaniu zgłoszenia."
            " Prosimy wysłać e-mail bądź skontaktować"
            " się drogą telefoniczną.",
        )


# Mapowanie rodzaju formularza na wartość modelu Rodzaje
# dla reverse mapping (edycja)
MODEL_RODZAJ_TO_FORM = {
    Zgloszenie_Publikacji.Rodzaje.ARTYKUL: "ARTYKUL",
    Zgloszenie_Publikacji.Rodzaje.MONOGRAFIA: "MONOGRAFIA",
    Zgloszenie_Publikacji.Rodzaje.ROZDZIAL_W_MONOGRAFII: "ROZDZIAL",
    Zgloszenie_Publikacji.Rodzaje.INNE: "POZOSTALE",
    # Legacy
    Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA: "ARTYKUL",
    Zgloszenie_Publikacji.Rodzaje.POZOSTALE: "POZOSTALE",
}

MODEL_FORMA_DOSTEPU_TO_FORM = {
    Zgloszenie_Publikacji.FormyDostepu.OTWARTY: "OTWARTY",
    Zgloszenie_Publikacji.FormyDostepu.OGRANICZONY: "OGRANICZONY",
}


class Zgloszenie_PublikacjiWizard(UczelniaSettingRequiredMixin, SessionWizardView):
    uczelnia_attr = "pokazuj_formularz_zglaszania_publikacji"

    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "protected", "zglos_publikacje")
    )
    form_list = [
        RodzajPublikacjiForm,  # "0"
        FormaDostepuForm,  # "1"
        Zgloszenie_Publikacji_DaneForm,  # "2"
        Zgloszenie_Publikacji_AutorFormSet,  # "3"
        Zgloszenie_Publikacji_KosztPublikacjiForm,  # "4"
    ]
    condition_dict = {
        "4": pokazuj_formularz_platnosci,
    }

    object = None

    def get_template_names(self):
        templates = {
            "0": "zglos_publikacje/step_rodzaj.html",
            "1": "zglos_publikacje/step_forma_dostepu.html",
            "2": "zglos_publikacje/step_dane.html",
            "3": "zglos_publikacje/step_autorzy.html",
            "4": "zglos_publikacje/step_platnosci.html",
        }
        return [templates[self.steps.current]]

    def dispatch(self, request, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia and uczelnia.wymagaj_logowania_zglos_publikacje:
            if not request.user.is_authenticated:
                from django.contrib.auth.views import (
                    redirect_to_login,
                )

                return redirect_to_login(request.get_full_path())

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == "2":
            step0 = self.get_cleaned_data_for_step("0") or {}
            step1 = self.get_cleaned_data_for_step("1") or {}
            kwargs["rodzaj"] = step0.get("rodzaj")
            kwargs["forma_dostepu"] = step1.get("forma_dostepu")
            # Pliki kroku 2 zapisujemy sami do extra_data (patrz
            # process_step_files) i NIE oddajemy ich do storage formtools,
            # więc przy rewalidacji w render_done `self.files` jest puste.
            # Flaga mówi formularzowi, że pliki już są — żeby wymóg
            # „min. 1 plik" dla OGRANICZONY nie wywalił submitu na końcu.
            kwargs["pliki_juz_zapisane"] = bool(
                self.storage.extra_data.get(self.PLIKI_EXTRA_KEY)
            )
        return kwargs

    def get_form_instance(self, step):
        kod_do_edycji = self.kwargs.get("kod_do_edycji")
        if kod_do_edycji:
            try:
                self.object = Zgloszenie_Publikacji.objects.get(
                    kod_do_edycji=kod_do_edycji
                )
            except Zgloszenie_Publikacji.DoesNotExist:
                raise Http404 from None

            # Tylko krok danych i autorów używa instancji
            if step in ("2", "3"):
                return self.object

        return None

    def _initial_dla_edycji_rodzaju(self):
        """Pre-populacja rodzaju przy edycji (krok 0)."""
        if not self.object:
            return None
        rodzaj_form = MODEL_RODZAJ_TO_FORM.get(self.object.rodzaj_zglaszanej_publikacji)
        if rodzaj_form:
            return {"rodzaj": rodzaj_form}
        return None

    def _initial_dla_edycji_formy_dostepu(self):
        """Pre-populacja formy dostepu przy edycji (krok 1)."""
        if not (self.object and self.object.forma_dostepu):
            return None
        forma_form = MODEL_FORMA_DOSTEPU_TO_FORM.get(self.object.forma_dostepu)
        if forma_form:
            return {"forma_dostepu": forma_form}
        return None

    def get_form_initial(self, step):
        edycja = self.kwargs.get("kod_do_edycji")

        if step == "0" and edycja:
            ret = self._initial_dla_edycji_rodzaju()
            if ret:
                return ret

        if step == "1" and edycja:
            ret = self._initial_dla_edycji_formy_dostepu()
            if ret:
                return ret

        if step == "2":
            user = self.request.user
            if user.is_authenticated and user.email != PUSTY_ADRES_EMAIL:
                return {"email": user.email}

        if step == "3":
            rok = self.request.session.get(const.SESSION_KEY)
            return [{"rok": rok}] * 512

        return super().get_form_initial(step)

    def process_step(self, form):
        if self.steps.current == "2":
            self.request.session[const.SESSION_KEY] = form.cleaned_data.get("rok")
        return super().process_step(form)

    PLIKI_EXTRA_KEY = "pliki_list"

    def process_step_files(self, form):
        """Zapisz wieloplikowe uploady poza standardowym storage formtools.

        `formtools.wizard.storage.base.set_step_files` iteruje
        `files.items()` po MultiValueDict, co dla pól typu
        `<input multiple>` gubi wszystkie pliki poza ostatnim
        (`.items()` zwraca jeden element per klucz). W rezultacie
        do `done()` docierał tylko ostatni z wgranych plików.

        Ratujemy się sami: każdy upload z `2-pliki` zapisujemy
        bezpośrednio do `file_storage` i przechowujemy listę
        metadanych w `storage.extra_data["pliki_list"]`. Standardowy
        storage formtools nadal dostaje `form.files` (bo z niego korzysta
        revalidacja w `render_done`), ale całość plików tworzymy
        w `done()` z `extra_data`.
        """
        files = form.files or {}
        if self.steps.current == "2" and hasattr(files, "getlist"):
            pliki_key = "2-pliki"
            pliki = files.getlist(pliki_key)
            if pliki:
                # Wyczyść poprzednie tmp pliki (powrót do kroku 2)
                self._wyczysc_tmp_pliki()
                saved = []
                for f in pliki:
                    tmp_name = self.file_storage.save(f.name, f)
                    saved.append(
                        {
                            "tmp_name": tmp_name,
                            "name": f.name,
                            "content_type": (
                                getattr(f, "content_type", None) or "application/pdf"
                            ),
                            "size": f.size,
                        }
                    )
                extra = self.storage.extra_data
                extra[self.PLIKI_EXTRA_KEY] = saved
                self.storage.extra_data = extra
            # NIE oddawaj `2-pliki` do formtools. Te pliki zapisaliśmy już
            # sami do `file_storage` (metadane w extra_data), a
            # `formtools.storage.set_step_files` zapisałby je PONOWNIE tym
            # samym storage. Dla plików > FILE_UPLOAD_MAX_MEMORY_SIZE Django
            # trzyma je jako TemporaryUploadedFile w /tmp i nasz pierwszy
            # zapis PRZENOSI plik z /tmp; drugi zapis otwierałby już
            # nieistniejącą ścieżkę → FileNotFoundError → HTTP 500.
            # Wymóg „min. 1 plik" przy rewalidacji w render_done pokrywa
            # flaga `pliki_juz_zapisane` (patrz get_form_kwargs).
            return MultiValueDict(
                {k: files.getlist(k) for k in files if k != "2-pliki"}
            )
        return super().process_step_files(form)

    def _wyczysc_tmp_pliki(self):
        """Usuń tymczasowe pliki z poprzedniego submita kroku 2."""
        extra = self.storage.extra_data
        for info in extra.get(self.PLIKI_EXTRA_KEY, []) or []:
            tmp_name = info.get("tmp_name")
            if not tmp_name:
                continue
            try:
                self.file_storage.delete(tmp_name)
            except FileNotFoundError:
                pass  # Już usunięty — nie problem
        extra[self.PLIKI_EXTRA_KEY] = []
        self.storage.extra_data = extra

    RODZAJ_ETYKIETY = {
        "ARTYKUL": "artykuł",
        "MONOGRAFIA": "książkę / monografię",
        "ROZDZIAL": "rozdział",
        "POZOSTALE": "inną publikację",
    }
    RODZAJ_IKONY = {
        "ARTYKUL": "📄",
        "MONOGRAFIA": "📚",
        "ROZDZIAL": "📖",
        "POZOSTALE": "📎",
    }
    FORMA_ETYKIETY = {
        "OTWARTY": "w otwartym dostępie",
        "OGRANICZONY": "w ograniczonym dostępie",
    }

    def _tytul_strony(self):
        step0 = self.get_cleaned_data_for_step("0") or {}
        rodzaj = step0.get("rodzaj")
        if not rodzaj:
            return "Zgłoś publikację"

        tytul = "Zgłaszasz: " + self.RODZAJ_ETYKIETY.get(rodzaj, rodzaj)

        step1 = self.get_cleaned_data_for_step("1") or {}
        forma = step1.get("forma_dostepu")
        if forma:
            tytul += " " + self.FORMA_ETYKIETY.get(forma, forma)

        return tytul

    BREADCRUMB_LABELS = {
        "0": "Rodzaj",
        "1": "Dostęp",
        "2": "Dane",
        "3": "Autorzy",
        "4": "Płatności",
    }

    def _wizard_breadcrumbs(self):
        current = int(self.steps.current)
        breadcrumbs = []
        for i in range(current + 1):
            step_str = str(i)
            breadcrumbs.append(
                {
                    "step": step_str,
                    "label": self.BREADCRUMB_LABELS.get(step_str, step_str),
                    "current": i == current,
                }
            )
        return breadcrumbs

    def get_context_data(self, form, **kwargs):
        if self.request.session.get(const.SESSION_KEY):
            kwargs["rok"] = self.request.session.get(const.SESSION_KEY)
        kwargs["tytul_strony"] = self._tytul_strony()
        kwargs["wizard_breadcrumbs"] = self._wizard_breadcrumbs()
        # Add banner for all steps after step 0
        if self.steps.current != "0":
            step0 = self.get_cleaned_data_for_step("0") or {}
            rodzaj = step0.get("rodzaj")
            if rodzaj:
                rodzaj_choices = dict(
                    RodzajPublikacjiForm.base_fields["rodzaj"].choices
                )
                kwargs["wybrany_rodzaj_ikona"] = self.RODZAJ_IKONY.get(rodzaj, "")
                kwargs["wybrany_rodzaj_label"] = rodzaj_choices.get(rodzaj, rodzaj)
        return super().get_context_data(form, **kwargs)

    @transaction.atomic
    def done(self, form_list, **kwargs):
        form_list = list(form_list)

        # Krok 0: rodzaj publikacji
        rodzaj_str = form_list[0].cleaned_data["rodzaj"]
        rodzaj_model = RODZAJ_FORM_TO_MODEL[rodzaj_str]

        # Krok 1: forma dostępu
        forma_str = form_list[1].cleaned_data["forma_dostepu"]
        forma_model = FORMA_DOSTEPU_FORM_TO_MODEL[forma_str]

        # Krok 2: dane publikacji
        dane = form_list[2].cleaned_data

        # Krok 3: autorzy (zawsze indeks 3)
        autorzy_formset = form_list[3]

        # Krok 4: opłaty (opcjonalnie)
        oplaty = {}
        if len(form_list) > 4:
            oplaty = form_list[4].cleaned_data

        # Utwórz lub aktualizuj obiekt
        if self.object is None:
            self.object = Zgloszenie_Publikacji(
                status=Zgloszenie_Publikacji.Statusy.NOWY
            )
        else:
            self.object.status = Zgloszenie_Publikacji.Statusy.PO_ZMIANACH
            self.object.kod_do_edycji = None
            self.object.przyczyna_zwrotu = ""

        # Ustaw rodzaj i formę dostępu
        self.object.rodzaj_zglaszanej_publikacji = rodzaj_model
        self.object.forma_dostepu = forma_model

        # Ustaw pola z formularza danych
        for field in [
            "tytul_oryginalny",
            "rok",
            "email",
            "strona_www",
        ]:
            if field in dane:
                setattr(self.object, field, dane[field])

        # Zgoda na publikację
        zgoda = dane.get("zgoda_na_publikacje_pelnego_tekstu")
        if zgoda is not None:
            self.object.zgoda_na_publikacje_pelnego_tekstu = zgoda

        # Wydawca (z QSS autocomplete)
        self._set_wydawca(dane)

        # Wydawnictwo nadrzędne (z QSS autocomplete)
        self._set_wydawnictwo_nadrzedne(dane)

        # Opłaty
        for field, value in oplaty.items():
            setattr(self.object, field, value)

        if self.request.user.is_authenticated and self.object.utworzyl_id is None:
            self.object.utworzyl = self.request.user

        if self.object.tytul_oryginalny:
            self.object.tytul_oryginalny = normalize_tytul_publikacji(
                self.object.tytul_oryginalny
            )

        self.object.save()

        # Obsługa plików (wiele plików)
        self._process_files(dane)

        # Autorzy
        typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.filter(
            typ_ogolny=TO_AUTOR
        ).first()

        if typ_odpowiedzialnosci is None:
            raise ValidationError(
                "Nie można utworzyć danych -- w systemie nie"
                " jest skonfigurowany żaden typ"
                " odpowiedzialnosci z typem ogólnym = autor."
            )

        _process_autorzy_formset(
            autorzy_formset,
            self.object,
            typ_odpowiedzialnosci,
        )

        transaction.on_commit(
            lambda: _send_notification_email(self.object, self.request)
        )

        return render(
            self.request,
            "zglos_publikacje/sukces.html",
            {
                "form_data": [form.cleaned_data for form in form_list],
                "object": self.object,
            },
        )

    def _set_wydawca(self, dane):
        """Ustaw pola wydawcy na podstawie danych z formularza."""
        if "wydawca" not in dane and "wydawca_zgloszenia" not in dane:
            return
        # Reset
        self.object.wydawca_bpp = None
        self.object.wydawca_pbn = None
        self.object.wydawca_zgloszenia = ""

        wydawca_val = dane.get("wydawca")
        if wydawca_val:
            instance, ct = _resolve_qss_value(wydawca_val)
            if isinstance(instance, Wydawca):
                self.object.wydawca_bpp = instance
                self.object.wydawca_zgloszenia = instance.nazwa
            elif isinstance(instance, PBN_Publisher):
                self.object.wydawca_pbn = instance
                self.object.wydawca_zgloszenia = instance.publisherName

        # Freetext fallback
        wydawca_tekst = dane.get("wydawca_zgloszenia", "").strip()
        if wydawca_tekst and not self.object.wydawca_zgloszenia:
            self.object.wydawca_zgloszenia = wydawca_tekst

    def _set_wydawnictwo_nadrzedne(self, dane):
        """Ustaw pola wyd. nadrzędnego z formularza."""
        # Reset
        self.object.wydawnictwo_nadrzedne_bpp = None
        self.object.wydawnictwo_nadrzedne_pbn = None
        self.object.wydawnictwo_nadrzedne_tekst = ""

        wn_val = dane.get("wydawnictwo_nadrzedne")
        if wn_val:
            instance, ct = _resolve_qss_value(wn_val)
            if isinstance(instance, Wydawnictwo_Zwarte):
                self.object.wydawnictwo_nadrzedne_bpp = instance
                self.object.wydawnictwo_nadrzedne_tekst = instance.tytul_oryginalny
            elif isinstance(instance, PBN_Publication):
                self.object.wydawnictwo_nadrzedne_pbn = instance
                self.object.wydawnictwo_nadrzedne_tekst = instance.title

        # Freetext fallback
        wn_tekst = dane.get("wydawnictwo_nadrzedne_tekst", "").strip()
        if wn_tekst and not self.object.wydawnictwo_nadrzedne_tekst:
            self.object.wydawnictwo_nadrzedne_tekst = wn_tekst

    def _process_files(self, dane):
        """Obsługa wielu plików PDF.

        Pliki zapisaliśmy w `process_step_files` do `file_storage`,
        a metadane wylądowały w `storage.extra_data[PLIKI_EXTRA_KEY]`.
        Tu odczytujemy listę i tworzymy dla każdego elementu rekord
        `Zgloszenie_Publikacji_Zalacznik`.

        Fallback do `dane["pliki"]` zostawiony dla scenariuszy
        z jednym plikiem (formtools storage trzyma jeden plik per
        klucz pola, więc to nigdy nie zwróci więcej niż jednego).
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        pliki_list = self.storage.extra_data.get(self.PLIKI_EXTRA_KEY) or []

        if pliki_list:
            for idx, info in enumerate(pliki_list):
                with self.file_storage.open(info["tmp_name"]) as fh:
                    content = fh.read()
                upload = SimpleUploadedFile(info["name"], content, info["content_type"])
                Zgloszenie_Publikacji_Zalacznik.objects.create(
                    zgloszenie=self.object,
                    plik=upload,
                    oryginalna_nazwa_pliku=skroc_nazwe_pliku(info["name"]),
                    kolejnosc=idx,
                )
            # Sprzątamy tmp pliki po przeniesieniu do permanent storage
            self._wyczysc_tmp_pliki()
            return

        # Fallback: pojedynczy plik z formtools storage
        files = dane.get("pliki") or []
        if not isinstance(files, list):
            files = [files]
        for idx, uploaded_file in enumerate(files):
            Zgloszenie_Publikacji_Zalacznik.objects.create(
                zgloszenie=self.object,
                plik=uploaded_file,
                oryginalna_nazwa_pliku=skroc_nazwe_pliku(uploaded_file.name),
                kolejnosc=idx,
            )
