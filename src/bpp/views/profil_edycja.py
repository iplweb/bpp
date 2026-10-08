"""Self-service edycja profilu autora (Faza 2, §3.8): biogram + zdjęcie.

Zalogowany użytkownik powiązany z rekordem ``Autor`` edytuje TYLKO własny
biogram (Markdown/HTML + podgląd na żywo) oraz zdjęcie. Układ podstrony jest
globalny per-Uczelnia i tu niedostępny (zarządza nim administrator).
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView, View

from bpp.models import Autor
from bpp.util.biogram import renderuj_biogram
from bpp.util.obrazy import MAKS_ROZMIAR_PLIKU_ZDJECIA, przetworz_zdjecie_autora


class AutorProfilForm(forms.ModelForm):
    class Meta:
        model = Autor
        fields = ["zdjecie", "biogram", "biogram_format"]

    def clean_zdjecie(self):
        """Waliduj rozmiar i przeskaluj świeżo wgrane zdjęcie (kwadrat WebP).

        Reużycie tej samej logiki co w adminie — jeden punkt prawdy dla
        przetwarzania zdjęcia. Niezmieniony plik przechodzi bez przetwarzania.
        """
        plik = self.cleaned_data.get("zdjecie")
        if not isinstance(plik, UploadedFile):
            return plik
        if plik.size > MAKS_ROZMIAR_PLIKU_ZDJECIA:
            raise forms.ValidationError("Maksymalny rozmiar pliku zdjęcia to 5 MB.")
        return przetworz_zdjecie_autora(plik, nazwa=plik.name)


class WymagajAutoraMixin(LoginRequiredMixin):
    """Dostęp tylko dla zalogowanego użytkownika z powiązanym ``user.autor``.

    Anonim → przekierowanie na login (LoginRequiredMixin). Zalogowany bez
    powiązanego autora → przekierowanie na „Mój profil" z komunikatem.
    """

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and getattr(request.user, "autor", None) is None
        ):
            messages.warning(
                request,
                "Twoje konto nie jest powiązane z autorem — nie ma czego edytować.",
            )
            return redirect("bpp:profil-uzytkownika")
        return super().dispatch(request, *args, **kwargs)


class ProfilEdycjaView(WymagajAutoraMixin, UpdateView):
    form_class = AutorProfilForm
    template_name = "bpp/profil_edycja.html"
    success_url = reverse_lazy("bpp:profil-uzytkownika")

    def get_object(self, queryset=None):
        return self.request.user.autor

    def form_valid(self, form):
        messages.success(self.request, "Zapisano zmiany w profilu.")
        return super().form_valid(form)


class ProfilBiogramPodgladView(WymagajAutoraMixin, View):
    """Serwerowy render podglądu biogramu (AJAX) — ten sam pipeline sanityzacji
    co przy zapisie, więc podgląd jest wierny i bezpieczny."""

    def post(self, request, *args, **kwargs):
        html = renderuj_biogram(
            request.POST.get("biogram", ""),
            request.POST.get("biogram_format", "md"),
        )
        return JsonResponse({"html": html})
