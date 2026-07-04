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
            from ewaluacja_metryki.uczelnia_scope import scope_metryki
            from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

            # Metryki pokazujemy z JEDNEJ uczelni — tej z requestu. Autor
            # afiliowany do wielu uczelni nie może widzieć tu metryk obcej
            # uczelni (no-op przy single-install).
            context["metryki"] = scope_metryki(
                MetrykaAutora.objects.filter(autor=autor),
                uczelnia_dla_odczytu(self.request),
            ).select_related("dyscyplina_naukowa")

        return context
