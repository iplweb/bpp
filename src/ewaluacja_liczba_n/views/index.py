import sys
import traceback

import rollbar
from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor_Dyscyplina, Uczelnia

from ..forms import SankcjeFormSet
from ..models import LiczbaNDlaUczelni
from ..utils import (
    oblicz_liczbe_n_na_koniec_2025,
    oblicz_liczby_n_dla_ewaluacji_2022_2025,
)


class LiczbaNIndexView(GroupRequiredMixin, TemplateView):
    """Główny widok aplikacji liczba N"""

    template_name = "ewaluacja_liczba_n/index.html"
    group_required = GR_WPROWADZANIE_DANYCH

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        uczelnia = Uczelnia.objects.get_default()

        # Pobierz wszystkie dane liczby N dla uczelni (średnia z 2022-2025)
        wszystkie_liczby_n = (
            LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia)
            .select_related("dyscyplina_naukowa")
            .order_by("-liczba_n")
        )

        # Oblicz liczby N na koniec 2025 dla każdej dyscypliny
        liczby_n_2025 = oblicz_liczbe_n_na_koniec_2025(uczelnia)

        # Dodaj liczby N na koniec 2025 do każdego obiektu i podziel na raportowane/nieraportowane
        liczby_n_raportowane = []
        liczby_n_nieraportowane = []

        for liczba in wszystkie_liczby_n:
            liczba.liczba_n_2025 = liczby_n_2025.get(liczba.dyscyplina_naukowa_id, 0)

            # Dyscyplina jest nieraportowana jeśli liczba N na koniec 2025 < 12
            if liczba.liczba_n_2025 < 12:
                liczby_n_nieraportowane.append(liczba)
            else:
                liczby_n_raportowane.append(liczba)

        context["liczby_n"] = liczby_n_raportowane
        context["dyscypliny_nieraportowane"] = liczby_n_nieraportowane

        # Formset do edycji sankcji
        context["formset"] = SankcjeFormSet(
            queryset=LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).order_by(
                "-liczba_n"
            )
        )

        # Słownik mapujący id obiektu LiczbaNDlaUczelni na formularz
        context["forms_by_id"] = {form.instance.pk: form for form in context["formset"]}

        # Oblicz sumę liczby N (średnia) - tylko dla dyscyplin raportowanych
        context["suma_liczby_n"] = sum(
            float(liczba.liczba_n) for liczba in liczby_n_raportowane
        )

        # Oblicz sumę sankcji - tylko dla dyscyplin raportowanych
        context["suma_sankcji"] = sum(
            float(liczba.sankcje or 0) for liczba in liczby_n_raportowane
        )

        # Oblicz sumę liczby N ostatecznej - tylko dla dyscyplin raportowanych
        context["suma_liczby_n_ostatecznej"] = sum(
            float(liczba.liczba_n_ostateczna) for liczba in liczby_n_raportowane
        )

        # Oblicz sumę liczby N na koniec 2025 - tylko dla dyscyplin raportowanych
        context["suma_liczby_n_2025"] = sum(
            float(liczba.liczba_n_2025) for liczba in liczby_n_raportowane
        )

        context["uczelnia"] = uczelnia
        return context


class ObliczLiczbeNView(GroupRequiredMixin, View):
    """Widok do obliczania liczby N"""

    group_required = GR_WPROWADZANIE_DANYCH

    def post(self, request, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_default()

        try:
            oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
            messages.success(
                request, "Pomyślnie obliczono liczbę N dla ewaluacji 2022-2025"
            )
        except Autor_Dyscyplina.DoesNotExist:
            traceback.print_exc()
            rollbar.report_exc_info(sys.exc_info())
            messages.error(
                request,
                "Błąd: Nie znaleziono danych Autor_Dyscyplina dla niektórych "
                "autorów. Upewnij się, że wszystkie dane są poprawnie "
                "wprowadzone w systemie.",
            )
        except NotImplementedError:
            traceback.print_exc()
            rollbar.report_exc_info()
            messages.error(
                request,
                "Błąd: Wykryto niespójność w danych - autor ma przypisane udziały "
                "dla dyscypliny która nie jest ani jego dyscypliną główną ani "
                "subdyscypliną. Odśwież tabelę Autor_Dyscyplina i spróbuj ponownie.",
            )
        except Exception as e:
            traceback.print_exc()
            rollbar.report_exc_info(sys.exc_info())
            messages.error(
                request,
                f"Błąd podczas obliczania liczby N: {str(e)}. "
                "Skontaktuj się z administratorem systemu.",
            )

        return HttpResponseRedirect(reverse("ewaluacja_liczba_n:index"))


class SaveSankcjeView(GroupRequiredMixin, View):
    """Widok do zapisywania sankcji dla wszystkich dyscyplin"""

    group_required = GR_WPROWADZANIE_DANYCH

    def post(self, request, *args, **kwargs):
        formset = SankcjeFormSet(request.POST)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Sankcje zostały zapisane.")
        else:
            messages.error(request, "Błąd podczas zapisywania sankcji.")
        return HttpResponseRedirect(reverse("ewaluacja_liczba_n:index"))
