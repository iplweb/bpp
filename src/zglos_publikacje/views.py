# Create your views here.
from django.db import transaction
from django.shortcuts import render
from django.views.generic import TemplateView
from formtools.wizard.views import SessionWizardView
from templated_email import send_templated_mail

from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.core import editors_emails


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"


from zglos_publikacje.forms import (
    Zgloszenie_Publikacji_DaneOgolneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
)


class Zgloszenie_PublikacjiWizard(SessionWizardView):
    template_name = "zglos_publikacje/zgloszenie_publikacji_form.html"
    form_list = [
        Zgloszenie_Publikacji_DaneOgolneForm,
        Zgloszenie_Publikacji_KosztPublikacjiForm,
    ]

    @transaction.atomic
    def done(self, form_list, **kwargs):
        self.object = Zgloszenie_Publikacji.objects.create(
            **(form_list[0].cleaned_data | form_list[1].cleaned_data)
        )

        def _():
            send_templated_mail(
                template_name="nowe_zgloszenie",
                from_email=self.object.email,
                recipient_list=editors_emails(),
                context={"object": self.object, "site_url": self.request.get_host()},
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
