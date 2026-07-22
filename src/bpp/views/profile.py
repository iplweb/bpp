from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from bpp.models import BppUser


class ProfilUstawieniaForm(forms.ModelForm):
    """Self-service ustawienia wyświetlania edytowalne przez użytkownika na
    jego własnej stronie profilu."""

    class Meta:
        model = BppUser
        fields = ["zwijaj_dlugie_listy_autorow"]


class ProfilUzytkownikaView(LoginRequiredMixin, TemplateView):
    template_name = "bpp/profil_uzytkownika.html"

    def get(self, request, *args, **kwargs):
        request.user.sprobuj_dopasowac_autora()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if "unlink_identity" in request.POST:
            return self._unlink_identity(request)

        if "unlink_orcid_identity" in request.POST:
            return self._unlink_orcid_identity(request)

        form = ProfilUstawieniaForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Ustawienia zostały zapisane.")
            return redirect(reverse("bpp:profil-uzytkownika"))
        return self.render_to_response(self.get_context_data(ustawienia_form=form))

    def _unlink_identity(self, request):
        """Odłącz wskazaną tożsamość SSO od konta użytkownika.

        Blokada self-lockout: konto bez używalnego hasła nie może odłączyć
        swojej OSTATNIEJ tożsamości OIDC — inaczej straciłoby jedyną drogę
        logowania. Odłączyć można tylko własną tożsamość.
        """
        user = request.user
        identity = user.oidc_identities.filter(
            pk=request.POST.get("unlink_identity")
        ).first()
        if identity is None:
            messages.error(request, "Nie znaleziono wskazanej tożsamości SSO.")
            return redirect(reverse("bpp:profil-uzytkownika"))

        if not user.has_usable_password() and user.oidc_identities.count() == 1:
            messages.error(
                request,
                "Nie można odłączyć ostatniej tożsamości SSO od konta bez "
                "hasła lokalnego — straciłbyś dostęp. Najpierw ustaw hasło.",
            )
            return redirect(reverse("bpp:profil-uzytkownika"))

        identity.delete()
        messages.success(request, "Tożsamość SSO została odłączona.")
        return redirect(reverse("bpp:profil-uzytkownika"))

    def _unlink_orcid_identity(self, request):
        """Odłącz wskazaną tożsamość ORCID od konta użytkownika.

        Blokada self-lockout: konto bez używalnego hasła nie może odłączyć
        swojej OSTATNIEJ tożsamości ORCID — inaczej straciłoby jedyną drogę
        logowania. Odłączyć można tylko własną tożsamość.
        """
        user = request.user
        identity = user.orcid_identities.filter(
            pk=request.POST.get("unlink_orcid_identity")
        ).first()
        if identity is None:
            messages.error(request, "Nie znaleziono wskazanej tożsamości ORCID.")
            return redirect(reverse("bpp:profil-uzytkownika"))

        if not user.has_usable_password() and user.orcid_identities.count() == 1:
            messages.error(
                request,
                "Nie można odłączyć ostatniej tożsamości ORCID od konta bez "
                "hasła lokalnego — straciłbyś dostęp. Najpierw ustaw hasło.",
            )
            return redirect(reverse("bpp:profil-uzytkownika"))

        identity.delete()
        messages.success(request, "Tożsamość ORCID została odłączona.")
        return redirect(reverse("bpp:profil-uzytkownika"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.setdefault("ustawienia_form", ProfilUstawieniaForm(instance=user))
        context["oidc_identities"] = user.oidc_identities.all()
        context["orcid_identities"] = user.orcid_identities.all()
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
