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
from ewaluacja_common.okres import okres_dla_request

from ..forms import SankcjeFormSet
from ..models import LiczbaNDlaUczelni
from ..utils import (
    oblicz_liczbe_n_na_koniec_okresu,
    oblicz_liczby_n_dla_okresu,
)


class LiczbaNIndexView(GroupRequiredMixin, TemplateView):
    """Główny widok aplikacji liczba N"""

    template_name = "ewaluacja_liczba_n/index.html"
    group_required = GR_WPROWADZANIE_DANYCH

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        okres = okres_dla_request(self.request)

        # Pobierz wszystkie dane liczby N dla uczelni (średnia z lat okresu)
        wszystkie_liczby_n = (
            LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia, okres=okres)
            .select_related("dyscyplina_naukowa")
            .order_by("-liczba_n")
        )

        # Oblicz liczby N na koniec okresu dla każdej dyscypliny
        liczby_n_koniec = oblicz_liczbe_n_na_koniec_okresu(uczelnia, okres=okres)

        # Dodaj liczby N na koniec okresu do każdego obiektu i podziel na
        # raportowane/nieraportowane
        liczby_n_raportowane = []
        liczby_n_nieraportowane = []

        for liczba in wszystkie_liczby_n:
            liczba.liczba_n_koniec = liczby_n_koniec.get(
                liczba.dyscyplina_naukowa_id, 0
            )

            # Dyscyplina jest nieraportowana jeśli liczba N na koniec okresu < 12
            if liczba.liczba_n_koniec < 12:
                liczby_n_nieraportowane.append(liczba)
            else:
                liczby_n_raportowane.append(liczba)

        context["liczby_n"] = liczby_n_raportowane
        context["dyscypliny_nieraportowane"] = liczby_n_nieraportowane

        # Formset do edycji sankcji
        context["formset"] = SankcjeFormSet(
            queryset=LiczbaNDlaUczelni.objects.filter(
                uczelnia=uczelnia, okres=okres
            ).order_by("-liczba_n")
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

        # Oblicz sumę liczby N na koniec okresu - tylko dla dyscyplin raportowanych
        context["suma_liczby_n_koniec"] = sum(
            float(liczba.liczba_n_koniec) for liczba in liczby_n_raportowane
        )

        context["uczelnia"] = uczelnia
        context["okres"] = okres
        return context


class ObliczLiczbeNView(GroupRequiredMixin, View):
    """Widok do obliczania liczby N"""

    group_required = GR_WPROWADZANIE_DANYCH

    def post(self, request, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(request)
        okres = okres_dla_request(request)

        try:
            oblicz_liczby_n_dla_okresu(uczelnia, okres=okres)
            messages.success(
                request, f"Pomyślnie obliczono liczbę N dla ewaluacji {okres}"
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
        uczelnia = Uczelnia.objects.get_for_request(request)
        formset = SankcjeFormSet(
            request.POST,
            queryset=LiczbaNDlaUczelni.objects.filter(
                uczelnia=uczelnia, okres=okres_dla_request(request)
            ),
        )
        if formset.is_valid():
            formset.save()
            messages.success(request, "Sankcje zostały zapisane.")
        else:
            messages.error(request, "Błąd podczas zapisywania sankcji.")
        return HttpResponseRedirect(reverse("ewaluacja_liczba_n:index"))
