# Create your views here.
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.shortcuts import render
from django.views.generic import TemplateView
from formtools.wizard.views import SessionWizardView
from messages_extends import messages
from sentry_sdk import capture_exception
from templated_email import send_templated_mail

from zglos_publikacje import const
from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.const import TO_AUTOR
from bpp.core import editors_emails
from bpp.models import Typ_Odpowiedzialnosci


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"


from zglos_publikacje.forms import (
    Zgloszenie_Publikacji_AutorFormSet,
    Zgloszenie_Publikacji_DaneOgolneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
    Zgloszenie_Publikacji_PlikFormSet,
)


class Zgloszenie_PublikacjiWizard(SessionWizardView):
    template_name = "zglos_publikacje/zgloszenie_publikacji_form.html"
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "zglos_publikacje")
    )
    form_list = [
        Zgloszenie_Publikacji_DaneOgolneForm,
        Zgloszenie_Publikacji_AutorFormSet,
        Zgloszenie_Publikacji_KosztPublikacjiForm,
        Zgloszenie_Publikacji_PlikFormSet,
    ]

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
        # Dla kroku "1" wstaw parametr rok:
        if step == "1":
            return [{"rok": self.request.session.get(const.SESSION_KEY)}]
        return super().get_form_initial(step)

    @transaction.atomic
    def done(self, form_list, **kwargs):
        self.object = Zgloszenie_Publikacji.objects.create(
            **(form_list[0].cleaned_data | form_list[2].cleaned_data)
        )

        typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.filter(
            typ_ogolny=TO_AUTOR
        ).first()

        if typ_odpowiedzialnosci is None:
            raise ValidationError(
                "Nie można utworzyć danych -- w systemie nie jest skonfigurowany "
                "żaden typ odpowiedzialnosci z typem ogólnym = autor."
            )

        autorzy_formset = form_list[1]

        if autorzy_formset.is_valid():
            for form in autorzy_formset:
                if form.is_valid():
                    if form.cleaned_data.get("DELETE"):
                        continue
                    else:
                        if not form.cleaned_data:
                            # Formularz może być zupełnie pusty
                            continue

                        instance = form.save(commit=False)
                        instance.rekord = self.object
                        instance.typ_odpowiedzialnosci = typ_odpowiedzialnosci
                        instance.save()

        pliki_formset = form_list[3]
        if pliki_formset.is_valid():
            for form in pliki_formset:
                if form.is_valid():
                    if form.cleaned_data.get("DELETE"):
                        continue
                    else:
                        instance = form.save(commit=False)
                        instance.rekord = self.object
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
