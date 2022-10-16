# Create your views here.
import operator
import os
from functools import reduce

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import Http404
from django.shortcuts import render
from django.views.generic import TemplateView
from formtools.wizard.views import SessionWizardView
from messages_extends import messages
from sentry_sdk import capture_exception
from templated_email import send_templated_mail

from import_common.normalization import normalize_tytul_publikacji
from zglos_publikacje import const
from zglos_publikacje.forms import (
    Zgloszenie_Publikacji_AutorFormSet,
    Zgloszenie_Publikacji_DaneOgolneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
    Zgloszenie_Publikacji_Plik,
)
from zglos_publikacje.models import (
    Obslugujacy_Zgloszenia_Wydzialow,
    Zgloszenie_Publikacji,
)

from bpp.const import PUSTY_ADRES_EMAIL, TO_AUTOR
from bpp.core import zgloszenia_publikacji_emails
from bpp.models import Typ_Odpowiedzialnosci, Uczelnia
from bpp.views.mixins import UczelniaSettingRequiredMixin


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"


def pokazuj_formularz_pliku(wizard):
    """Jeżeli w pierwszym kroku podano prawidłowy adres URL dla strony WWW, to nie pytaj
    o plik. Jeżeli nie podano - pytaj."""
    cleaned_data = wizard.get_cleaned_data_for_step("0") or {}
    return not cleaned_data.get("strona_www", None)


def pokazuj_formularz_platnosci(wizard):
    # Jeżeli dla uczelni wyłączono potrzebę wpisywania informacji o płatnościach to nie pokazuj
    # tego formularza:

    uczelnia = Uczelnia.objects.get_for_request(wizard.request)
    if uczelnia is not None:
        if uczelnia.wymagaj_informacji_o_oplatach is not True:
            return False

    # OK, nie wyłączono globalnie podawania informacji o opłaach

    # Jeżeli w pierwszym kroku podano rodzaj publikacji jako artykuł naukowy lub monografia
    # to zapytaj o koszta. Jeżeli rodzaj jest inny -- to nie pytaj
    cleaned_data = wizard.get_cleaned_data_for_step("0") or {}
    return (
        cleaned_data.get("rodzaj_zglaszanej_publikacji", None)
        == Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    )


class Zgloszenie_PublikacjiWizard(UczelniaSettingRequiredMixin, SessionWizardView):
    uczelnia_attr = "pokazuj_formularz_zglaszania_publikacji"

    template_name = "zglos_publikacje/zgloszenie_publikacji_form.html"
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "zglos_publikacje")
    )
    form_list = [
        Zgloszenie_Publikacji_DaneOgolneForm,
        Zgloszenie_Publikacji_Plik,
        Zgloszenie_Publikacji_AutorFormSet,
        Zgloszenie_Publikacji_KosztPublikacjiForm,
    ]
    condition_dict = {"1": pokazuj_formularz_pliku, "3": pokazuj_formularz_platnosci}

    object = None

    def get_form_instance(self, step):
        kod_do_edycji = self.kwargs.get("kod_do_edycji")
        if kod_do_edycji:
            try:
                self.object = Zgloszenie_Publikacji.objects.get(
                    kod_do_edycji=kod_do_edycji
                )
            except Zgloszenie_Publikacji.DoesNotExist:
                raise Http404

            return {
                "0": self.object,
                "1": self.object,
                "2": self.object,
                "3": self.object,
            }[step]

    def process_step(self, form):
        if self.steps.current == "0":
            # Dla pierwszego formularza zapisz wartość roku w sesji:
            self.request.session[const.SESSION_KEY] = form.cleaned_data.get("rok")
        return super().process_step(form)

    def get_context_data(self, form, **kwargs):
        if self.request.session.get(const.SESSION_KEY):
            # Jeżeli wartość roku jest w sesji, to zwróć go do kontekstu:
            kwargs["rok"] = self.request.session.get(const.SESSION_KEY)
        return super().get_context_data(form, **kwargs)

    def get_form_initial(self, step):
        # Dla kroku "0" jeżeli użytkownik ma poprawny e-mail, to go użyj:
        if step == "0":
            if self.request.user.is_authenticated:
                if self.request.user.email != PUSTY_ADRES_EMAIL:
                    return {"email": self.request.user.email}

        # Dla kroku "2" (autorzy, dyscypliny) wstaw parametr rok:
        if step == "2":
            return [{"rok": self.request.session.get(const.SESSION_KEY)}] * 512
        return super().get_form_initial(step)

    @transaction.atomic
    def done(self, form_list, **kwargs):
        dane_rekordu = form_list[0].cleaned_data

        rest_of_data = {}

        if dane_rekordu.get("strona_www"):
            # Dodający podał stronę WWW --  wiec nie było pytania o plik -- wiec formularz [1] to
            # lista autorów, a pozostałe formularze zaczną się od [2]
            autorset_form_list = 1

            pozostale_formularze = [form.cleaned_data for form in form_list[2:]]
            if pozostale_formularze:
                rest_of_data = reduce(operator.or_, pozostale_formularze)
        else:
            # Dodający NIE podał strony WWW, czyli formularz [1] zawiera dane o pliku,
            # [2] to lista autorów a formularz [3] i kolejne...
            autorset_form_list = 2

            rest_of_data = reduce(
                operator.or_,
                [
                    form_list[1].cleaned_data,
                ]
                + [form.cleaned_data for form in form_list[3:]],
            )

        kwargs = dane_rekordu | rest_of_data

        if self.object is None:
            self.object = Zgloszenie_Publikacji(
                status=Zgloszenie_Publikacji.Statusy.NOWY
            )
        else:
            # Jezeli obiekt już istniał w bazie, to oznacza, że jest edytowany przez zgłaszającego
            # czyli należy dać mu status PO_ZMIANACH:
            self.object.status = Zgloszenie_Publikacji.Statusy.PO_ZMIANACH

            # Ustaw kod_do_edycji na pusty; jeżeli obiekt jest edytowany, to wyczyszczenie tego pola uniemożliwi
            # ponowne wejście w edycję.
            self.object.kod_do_edycji = None

            # Zresetuj przyczynę zwrotu -- rekord został zmodyfikowany
            self.object.przyczyna_zwrotu = None

        for attr_name, value in kwargs.items():
            setattr(self.object, attr_name, value)

        if self.request.user.is_authenticated and self.object.utworzyl_id is None:
            self.object.utworzyl = self.request.user

        if self.object.tytul_oryginalny:
            # Jeżeli jest tytuł oryginalny, to znormalizuj go, m.in. wycinając znaki
            # newline, ponieważ django-templated-email w wersji 3.0.0 nie obsługuje ich,
            # ma to poprawione w trunku, po nowym release można zaktualizować django-templated-email
            # i pozbyć się tego kodu
            #
            # https://github.com/vintasoftware/django-templated-email/issues/138

            self.object.tytul_oryginalny = normalize_tytul_publikacji(
                self.object.tytul_oryginalny
            )

        self.object.save()

        typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.filter(
            typ_ogolny=TO_AUTOR
        ).first()

        if typ_odpowiedzialnosci is None:
            raise ValidationError(
                "Nie można utworzyć danych -- w systemie nie jest skonfigurowany "
                "żaden typ odpowiedzialnosci z typem ogólnym = autor."
            )

        autorzy_formset = form_list[autorset_form_list]

        if autorzy_formset.is_valid():
            for no, form in enumerate(autorzy_formset):
                if form.is_valid():
                    if form.cleaned_data.get("DELETE"):
                        if form.instance.pk:
                            form.instance.delete()
                        continue
                    else:
                        if not form.cleaned_data:
                            # Formularz może być zupełnie pusty
                            continue

                        instance = form.save(commit=False)
                        instance.rekord = self.object
                        instance.kolejnosc = no
                        instance.typ_odpowiedzialnosci = typ_odpowiedzialnosci
                        instance.save()

        def _():
            recipient_list = None

            # Wybór autora i jednostki.
            #
            # Szukamy pierwszej, nie-obcej jednostki, skupiającej pracowników.
            # Jeżeli nie znajdziemy takiej, używamy obcej.

            jednostka_do_powiadomienia = None

            for zpa in self.object.zgloszenie_publikacji_autor_set.all().select_related(
                "jednostka"
            ):
                if zpa.jednostka_id is not None:
                    jednostka_do_powiadomienia = zpa.jednostka

                if jednostka_do_powiadomienia.skupia_pracownikow:
                    break

            if jednostka_do_powiadomienia is not None:
                recipient_list = (
                    Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_wydzialu(
                        jednostka_do_powiadomienia.wydzial
                    )
                )

            if not recipient_list:
                recipient_list = zgloszenia_publikacji_emails()

            try:
                send_templated_mail(
                    template_name="nowe_zgloszenie",
                    from_email=getattr(
                        settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"
                    ),
                    headers={"reply-to": self.object.email},
                    recipient_list=recipient_list,
                    context={
                        "object": self.object,
                        "site_url": self.request.get_host(),
                    },
                )
            except Exception as e:
                capture_exception(e)

                messages.add_message(
                    self.request,
                    messages.WARNING,
                    "Z uwagi na błąd wysyłania komunikatu z powiadomieniem, zespół Biblioteki nie "
                    "został powiadomiony o dodaniu zgłoszenia. Prosimy wysłać e-mail bądź skontaktować się drogą "
                    "telefoniczną.",
                )

        transaction.on_commit(_)

        return render(
            self.request,
            "zglos_publikacje/sukces.html",
            {
                "form_data": [form.cleaned_data for form in form_list],
                "object": self.object,
            },
        )
