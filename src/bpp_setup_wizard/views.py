"""Krok 3 kreatora pierwszego uruchomienia: integracja z PBN (FD#499).

Krok zaczyna się od pytania „Czy masz już nazwę i token aplikacji z PBN?"
z trzema odpowiedziami (parametr ``?odpowiedz=``). Formularz PBN widać tylko
po „Tak"; „później" i „nie wiem" pozwalają pominąć krok. Każda ścieżka
gasi ``Uczelnia.kreator_czeka_na_pbn`` i kończy kreator — brak danych PBN
nie blokuje startu systemu. To widok kroku silnika ``PbnSetupStep``.
"""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView
from first_run_wizard.models import FirstRunWizardState
from first_run_wizard.registry import registry

from bpp.models import Uczelnia
from bpp_setup_wizard.forms import PbnSetupForm
from bpp_setup_wizard.steps import PbnSetupStep

ODPOWIEDZ_TAK = "tak"
ODPOWIEDZ_POZNIEJ = "pozniej"
ODPOWIEDZ_NIE_WIEM = "nie-wiem"
ODPOWIEDZI = (ODPOWIEDZ_TAK, ODPOWIEDZ_POZNIEJ, ODPOWIEDZ_NIE_WIEM)

AKCJA_ZAPISZ = "zapisz"
AKCJA_POMIN = "pomin"


class PbnSetupView(FormView):
    form_class = PbnSetupForm
    template_name = "bpp_setup_wizard/pbn_setup.html"

    def dispatch(self, request, *args, **kwargs):
        if FirstRunWizardState.is_completed():
            # Kreator zamknięty (także po świadomym pominięciu PBN) — krok
            # nie wraca; dane PBN edytuje się w Administracja → Uczelnia.
            raise Http404
        if registry.get(PbnSetupStep.name).is_complete():
            # Na pytanie o PBN już odpowiedziano — middleware poprowadzi dalej.
            return redirect("/")
        user = request.user
        if not (user.is_authenticated and user.is_superuser):
            return redirect("/")
        self.uczelnia = Uczelnia.objects.get_for_request(request)
        if self.uczelnia is None:
            # Krok 2 jeszcze nie zrobiony — middleware poprowadzi dalej.
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get_odpowiedz(self):
        if self.request.method == "POST" and (
            self.request.POST.get("akcja") == AKCJA_ZAPISZ
        ):
            return ODPOWIEDZ_TAK
        odpowiedz = self.request.GET.get("odpowiedz")
        return odpowiedz if odpowiedz in ODPOWIEDZI else None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.uczelnia
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_url = reverse("bpp_setup_wizard:pbn")
        ctx.update(
            {
                "title": "Integracja z PBN",
                "odpowiedz": self.get_odpowiedz(),
                "url_pytania": base_url,
                "url_tak": f"{base_url}?odpowiedz={ODPOWIEDZ_TAK}",
                "url_pozniej": f"{base_url}?odpowiedz={ODPOWIEDZ_POZNIEJ}",
                "url_nie_wiem": f"{base_url}?odpowiedz={ODPOWIEDZ_NIE_WIEM}",
                "url_admin_uczelnia": reverse(
                    "admin:bpp_uczelnia_change", args=(self.uczelnia.pk,)
                ),
            }
        )
        return ctx

    def post(self, request, *args, **kwargs):
        if request.POST.get("akcja") == AKCJA_POMIN:
            return self.zakoncz()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        return self.zakoncz()

    def zakoncz(self):
        # Odpowiedź (zapis albo pominięcie) zamyka krok PBN — dla wszystkich
        # czekających uczelni, żeby krok nie utknął, gdyby uczelnia z requestu
        # była inna niż ta utworzona w kroku 2.
        Uczelnia.objects.filter(kreator_czeka_na_pbn=True).update(
            kreator_czeka_na_pbn=False
        )
        # Zapamiętaj zakończenie kreatora od razu, nie czekając na kolejny
        # request przez middleware.
        if registry.inspect().all_complete:
            FirstRunWizardState.mark_completed()
        return redirect("/")
