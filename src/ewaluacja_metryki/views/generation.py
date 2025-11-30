from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View

from ewaluacja_common.models import Rodzaj_Autora

from ..models import StatusGenerowania
from ..tasks import generuj_metryki_task_parallel
from .mixins import ma_uprawnienia_ewaluacji


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class UruchomGenerowanieView(View):
    """Widok do uruchamiania generowania metryk przez Celery task"""

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponse
        from django.shortcuts import render

        # Dodatkowe sprawdzenie uprawnień do generowania (tylko staff)
        if not request.user.is_staff:
            if request.headers.get("HX-Request"):
                # Dla HTMX zwróć błąd
                response = HttpResponse(
                    "Nie masz uprawnień do uruchomienia generowania."
                )
                response["HX-Trigger"] = '{"showError": "No permissions"}'
                return response
            messages.error(request, "Nie masz uprawnień do uruchomienia generowania.")
            return redirect("ewaluacja_metryki:lista")

        # Sprawdź czy generowanie nie jest już w trakcie
        status = StatusGenerowania.get_or_create()
        if status.w_trakcie:
            if request.headers.get("HX-Request"):
                # Dla HTMX zwróć aktualny status
                return render(
                    request,
                    "ewaluacja_metryki/partials/status_box.html",
                    {"status_generowania": status, "progress_procent": 0},
                )
            messages.warning(
                request,
                f"Generowanie jest już w trakcie (rozpoczęte: "
                f"{status.data_rozpoczecia.strftime('%Y-%m-%d %H:%M:%S')})",
            )
            return redirect("ewaluacja_metryki:lista")

        # Pobierz parametry z formularza (jeśli są)
        rok_min = int(request.POST.get("rok_min", 2022))
        rok_max = int(request.POST.get("rok_max", 2025))
        minimalny_pk = float(request.POST.get("minimalny_pk", 0.01))
        nadpisz = request.POST.get("nadpisz", "on") == "on"

        # Pobierz zaznaczone rodzaje autorów
        rodzaje_autora = request.POST.getlist("rodzaj_autora")
        if not rodzaje_autora:
            # Domyślnie wszystkie rodzaje z licz_sloty=True jeśli nic nie zaznaczono
            rodzaje_autora = list(
                Rodzaj_Autora.objects.filter(licz_sloty=True).values_list(
                    "skrot", flat=True
                )
            )

        # Oblicz liczbę autorów do przetworzenia (aby ustawić status od razu)
        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

        total_count = IloscUdzialowDlaAutoraZaCalosc.objects.all().count()

        # Uruchom równoległy task (z domyślnym przeliczaniem liczby N)
        result = generuj_metryki_task_parallel.delay(
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=minimalny_pk,
            nadpisz=nadpisz,
            przelicz_liczbe_n=True,  # Zawsze przeliczaj liczbę N przy generowaniu metryk
            rodzaje_autora=rodzaje_autora,
        )

        # KLUCZOWE: Ustaw status w_trakcie=True OD RAZU w widoku
        # (task będzie tylko aktualizował postęp, nie rozpoczynał od nowa)
        status.rozpocznij_generowanie(
            task_id=str(result.id), liczba_do_przetworzenia=total_count
        )

        # Jeśli to żądanie HTMX, zwróć fragment HTML ze statusem
        if request.headers.get("HX-Request"):
            # Status już jest ustawiony powyżej
            context = {
                "status_generowania": status,
                "progress_procent": 0,
            }
            response = render(
                request, "ewaluacja_metryki/partials/status_box.html", context
            )
            # Używamy angielskiego triggerera aby uniknąć problemów z kodowaniem MIME
            # Komunikat po polsku będzie generowany po stronie JavaScript
            import json

            trigger_data = {"metricsStarted": True, "taskId": str(result.id)}
            response["HX-Trigger"] = json.dumps(trigger_data)
            return response

        # Dla zwykłego żądania zachowaj kompatybilność wsteczną
        messages.success(
            request,
            f"Generowanie metryk zostało uruchomione (ID zadania: {result.id}). "
            "Odśwież stronę za chwilę, aby zobaczyć postęp.",
        )

        return redirect("ewaluacja_metryki:lista")

    def get(self, request, *args, **kwargs):
        # GET przekierowuje do listy
        return redirect("ewaluacja_metryki:lista")


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class StatusGenerowaniaView(View):
    """Widok zwracający status generowania jako JSON (dla AJAX)"""

    def get(self, request, *args, **kwargs):
        status = StatusGenerowania.get_or_create()

        return JsonResponse(
            {
                "w_trakcie": status.w_trakcie,
                "data_rozpoczecia": (
                    status.data_rozpoczecia.isoformat()
                    if status.data_rozpoczecia
                    else None
                ),
                "data_zakonczenia": (
                    status.data_zakonczenia.isoformat()
                    if status.data_zakonczenia
                    else None
                ),
                "liczba_przetworzonych": status.liczba_przetworzonych,
                "liczba_bledow": status.liczba_bledow,
                "ostatni_komunikat": status.ostatni_komunikat,
                "procent": (
                    round(
                        (
                            status.liczba_przetworzonych
                            / status.liczba_do_przetworzenia
                            * 100
                        ),
                        1,
                    )
                    if status.w_trakcie and status.liczba_do_przetworzenia > 0
                    else 0
                ),
                "liczba_do_przetworzenia": status.liczba_do_przetworzenia,
            }
        )


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class StatusGenerowaniaPartialView(View):
    """Widok zwracający częściowy HTML ze statusem generowania dla HTMX"""

    def get(self, request, *args, **kwargs):
        from django.shortcuts import render

        # Pobierz status generowania
        status = StatusGenerowania.get_or_create()

        # Sprawdź czy poprzedni status był w trakcie (dla odświeżenia strony po zakończeniu)
        previous_status_was_running = (
            request.session.get("generation_was_running", False)
            if not status.w_trakcie
            else False
        )

        # Zapamiętaj aktualny stan
        request.session["generation_was_running"] = status.w_trakcie

        # Oblicz procent postępu
        progress_procent = 0
        if status.w_trakcie and status.liczba_do_przetworzenia > 0:
            progress_procent = round(
                (status.liczba_przetworzonych / status.liczba_do_przetworzenia * 100), 1
            )

        # Kontekst dla szablonu
        context = {
            "status_generowania": status,
            "progress_procent": progress_procent,
            "previous_status_was_running": previous_status_was_running,
        }

        return render(request, "ewaluacja_metryki/partials/status_box.html", context)
