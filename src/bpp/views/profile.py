from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class ProfilUzytkownikaView(LoginRequiredMixin, TemplateView):
    template_name = "bpp/profil_uzytkownika.html"

    def get(self, request, *args, **kwargs):
        request.user.sprobuj_dopasowac_autora()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        autor = getattr(user, "autor", None)
        context["autor"] = autor

        if autor:
            from ewaluacja_metryki.models import MetrykaAutora

            context["metryki"] = MetrykaAutora.objects.filter(
                autor=autor
            ).select_related("dyscyplina_naukowa")

        return context
