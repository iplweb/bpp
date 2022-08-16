# Create your views here.
import os

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

from zglos_publikacje import const
from zglos_publikacje.forms import (
    Zgloszenie_Publikacji_AutorFormSet,
    Zgloszenie_Publikacji_DaneOgolneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
    Zgloszenie_Publikacji_Plik,
)
from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.const import TO_AUTOR
from bpp.core import editors_emails
from bpp.models import Typ_Odpowiedzialnosci


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"


def pokazuj_formularz_pliku(wizard):
    """Jeżeli w pierwszym kroku podano prawidłowy adres URL dla strony WWW, to nie pytaj
    o plik. Jeżeli nie podano - pytaj."""
    cleaned_data = wizard.get_cleaned_data_for_step("0") or {}
    return not cleaned_data.get("strona_www", None)


class Zgloszenie_PublikacjiWizard(SessionWizardView):
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
    condition_dict = {"1": pokazuj_formularz_pliku}

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
        # Dla kroku "2" (autorzy, dyscypliny) wstaw parametr rok:
        if step == "2":
            return [{"rok": self.request.session.get(const.SESSION_KEY)}]
        return super().get_form_initial(step)

    @transaction.atomic
    def done(self, form_list, **kwargs):
        dane_rekordu = form_list[0].cleaned_data
        if dane_rekordu.get("strona_www"):
            autorset_form_list = 1
            rest_of_data = form_list[2].cleaned_data
        else:
            # Dodający podał stronę WWW --  wiec nie było pytania o plik -- wiec formularz [1] to
            # autorzy, a następny formularz [2] to lista autorów...
            autorset_form_list = 2
            rest_of_data = form_list[1].cleaned_data | form_list[3].cleaned_data

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
            try:
                send_templated_mail(
                    template_name="nowe_zgloszenie",
                    from_email=self.object.email,
                    recipient_list=editors_emails(),
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
