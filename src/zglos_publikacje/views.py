# Create your views here.
from django.db import transaction
from django.views.generic import CreateView, TemplateView
from templated_email import send_templated_mail

from zglos_publikacje.forms import Zgloszenie_PublikacjiForm
from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.core import editors_emails


class DodajZgloszenie_Publikacji(CreateView):
    model = Zgloszenie_Publikacji
    form_class = Zgloszenie_PublikacjiForm

    def get_success_url(self):
        return "../sukces"

    def form_valid(self, form):
        ret = super().form_valid(form)

        def _():
            send_templated_mail(
                template_name="nowe_zgloszenie",
                from_email=self.object.email,
                recipient_list=editors_emails(),
                context={"object": self.object, "site_url": self.request.get_host()},
            )

        transaction.on_commit(_)
        return ret


class Sukces(TemplateView):
    template_name = "zglos_publikacje/sukces.html"
