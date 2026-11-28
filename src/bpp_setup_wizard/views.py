"""Widoki kroków kreatora: dane demonstracyjne oraz integracja z PBN.

Integracja z PBN (FD#499):

Krok zaczyna się od pytania „Czy masz już nazwę i token aplikacji z PBN?"
z trzema odpowiedziami (parametr ``?odpowiedz=``). Formularz PBN widać tylko
po „Tak"; „później" i „nie wiem" pozwalają pominąć krok. Każda ścieżka
gasi ``Uczelnia.kreator_czeka_na_pbn`` i kończy kreator — brak danych PBN
nie blokuje startu systemu. To widok kroku silnika ``PbnSetupStep``.
"""

from __future__ import annotations

from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import FormView
from first_run_wizard.models import FirstRunWizardState
from first_run_wizard.registry import registry

from bpp.models import Uczelnia
from bpp_setup_wizard import dane_demo
from bpp_setup_wizard.forms import DaneDemoForm, PbnSetupForm
from bpp_setup_wizard.models import KreatorDanychDemo
from bpp_setup_wizard.steps import DaneDemoSetupStep, PbnSetupStep

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


# --- Krok „Dane demonstracyjne” --------------------------------------------

AKCJA_NIE = "nie"
AKCJA_GENERUJ = "generuj"
AKCJA_DALEJ = "dalej"


def _jest_superuserem(user) -> bool:
    return bool(user.is_authenticated and user.is_superuser)


class DaneDemoView(View):
    """Krok „Dane demonstracyjne”: pytanie → wybór motywu → postęp/błąd.

    Strona zależy od stanu ostatniej operacji generowania:

    * w toku — ekran postępu (odpytuje ``DaneDemoPostepView``),
    * błąd, po którym dane zostały w bazie — ekran błędu z przyciskiem
      „Przejdź dalej”,
    * brak / błąd z usuniętymi danymi — pytanie „Utworzyć dane demo?”,
      a po ``?odpowiedz=tak`` wybór motywu.
    """

    template_name = "bpp_setup_wizard/dane_demo.html"

    def dispatch(self, request, *args, **kwargs):
        if FirstRunWizardState.is_completed():
            raise Http404
        if not _jest_superuserem(request.user):
            return redirect("/")
        if registry.get(DaneDemoSetupStep.name).is_complete():
            # Decyzja już podjęta — middleware poprowadzi dalej.
            return redirect("/")
        self.operacja = dane_demo.ostatnie_generowanie()
        return super().dispatch(request, *args, **kwargs)

    @property
    def url(self) -> str:
        return reverse("bpp_setup_wizard:dane_demo")

    def tryb(self) -> str:
        op = self.operacja
        if op is not None and op.w_toku:
            return "postep"
        if (
            op is not None
            and op.get_state() != "FINISHED_OK"
            and not (op.dane_usuniete or op.blad_zaakceptowany)
        ):
            return "blad"
        if self.request.GET.get("odpowiedz") == "tak":
            return "motyw"
        return "pytanie"

    def render(self, form=None, status=200):
        tryb = self.tryb()
        op = self.operacja
        ctx = {
            "title": DaneDemoSetupStep.verbose_name,
            "tryb": tryb,
            "operacja": op,
            "form": form if form is not None else DaneDemoForm(),
            "url_pytania": self.url,
            "url_tak": f"{self.url}?odpowiedz=tak",
            "url_postepu": reverse("bpp_setup_wizard:dane_demo_postep"),
            "liczba_autorow": dane_demo.PARAMETRY_GENERATORA["autorow"],
            "liczba_prac": dane_demo.PARAMETRY_GENERATORA["ile_ciaglych"]
            + dane_demo.PARAMETRY_GENERATORA["ile_zwartych"],
            # Błąd poprzedniej próby, po którym częściowe dane usunięto —
            # pokazujemy go nad pytaniem.
            "poprzedni_blad": (
                op
                if op is not None
                and tryb in ("pytanie", "motyw")
                and op.get_state() == "FINISHED_ERROR"
                else None
            ),
        }
        return render(self.request, self.template_name, ctx, status=status)

    def get(self, request, *args, **kwargs):
        return self.render()

    def post(self, request, *args, **kwargs):
        akcja = request.POST.get("akcja")
        tryb = self.tryb()

        if tryb == "postep":
            # Podwójne kliknięcie, przeładowanie po POST-cie, druga karta —
            # generowanie już trwa, pokaż jego postęp.
            return redirect(self.url)

        if akcja == AKCJA_DALEJ and tryb == "blad":
            self.operacja.blad_zaakceptowany = True
            self.operacja.save(update_fields=["blad_zaakceptowany"])
            return redirect("/")

        if tryb == "blad":
            return redirect(self.url)

        if akcja == AKCJA_NIE:
            with transaction.atomic():
                # Ta sama blokada co przy starcie generowania: „Nie” z jednej
                # karty i „Utwórz” z drugiej nie przeplotą się.
                kreator = KreatorDanychDemo.zablokuj()
                ostatnie = dane_demo.ostatnie_generowanie()
                if ostatnie is not None and ostatnie.w_toku:
                    return redirect(self.url)
                kreator.odpowiedz = KreatorDanychDemo.ODPOWIEDZ_NIE
                kreator.odpowiedziano = timezone.now()
                kreator.save()
            return redirect("/")

        if akcja == AKCJA_GENERUJ:
            form = DaneDemoForm(request.POST)
            if not form.is_valid():
                return self.render(form=form)
            try:
                dane_demo.rozpocznij_generowanie(
                    request.user, form.cleaned_data["motyw"]
                )
            except dane_demo.GenerowanieNiedozwolone as e:
                form.add_error(None, str(e))
                return self.render(form=form)
            return redirect(self.url)

        return redirect(self.url)


class DaneDemoPostepView(View):
    """Stan generowania danych demo (JSON) dla strony postępu kreatora.

    Działa także po zakończeniu kreatora — strona postępu może dopytać
    o wynik, zanim przekieruje do BPP."""

    def get(self, request, *args, **kwargs):
        if not _jest_superuserem(request.user):
            return JsonResponse({"blad": "Brak uprawnień."}, status=403)
        op = dane_demo.ostatnie_generowanie()
        if op is None:
            return JsonResponse({"stan": "BRAK"})
        ostatnio = op.postep_zaktualizowano or op.started_on or op.created_on
        return JsonResponse(
            {
                "stan": op.get_state(),
                "procent": op.percent,
                "opis": op.status_text,
                "w_toku": op.w_toku,
                "zawieszone": op.w_toku
                and timezone.now() - ostatnio > dane_demo.PROG_ZAWIESZENIA,
                "blad": op.ostatnia_linia_bledu,
                "url_dalej": "/",
                "url_kroku": reverse("bpp_setup_wizard:dane_demo"),
            }
        )
