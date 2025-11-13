from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, View

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Wydawnictwo_Ciagle, Zrodlo

from .forms import PrzemapowaZrodloForm
from .models import PrzemapowaZrodla


class WprowadzanieDanychRequiredMixin(UserPassesTestMixin):
    """Mixin sprawdzający czy użytkownik należy do grupy 'wprowadzanie danych' lub jest superuserem."""

    def test_func(self):
        # Sprawdź czy użytkownik jest zalogowany
        if not self.request.user.is_authenticated:
            return False

        # Sprawdź czy użytkownik jest superuserem
        if self.request.user.is_superuser:
            return True

        # Sprawdź czy użytkownik należy do grupy 'wprowadzanie danych'
        # Użyj cached_groups jeśli dostępne (dla optymalizacji), w przeciwnym wypadku fallback
        if hasattr(self.request.user, "cached_groups"):
            return GR_WPROWADZANIE_DANYCH in [
                x.name for x in self.request.user.cached_groups
            ]
        else:
            return self.request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()

    def handle_no_permission(self):
        messages.error(
            self.request,
            "Nie masz uprawnień do przemapowywania źródeł. "
            "Funkcja dostępna tylko dla grupy 'wprowadzanie danych' oraz superuserów.",
        )
        return redirect("bpp:browse_zrodla")


class PrzemapujZrodloView(WprowadzanieDanychRequiredMixin, FormView):
    """Widok do przemapowania publikacji z jednego źródła do drugiego."""

    template_name = "przemapuj_zrodlo/przemapuj.html"
    form_class = PrzemapowaZrodloForm

    def dispatch(self, request, *args, **kwargs):
        # Pobierz źródło źródłowe i sprawdź czy ma publikacje
        self.zrodlo_zrodlowe = get_object_or_404(
            Zrodlo.objects.select_related("pbn_uid"), slug=self.kwargs["slug"]
        )

        # Sprawdź czy źródło można przemapować (nie ma MNISW ID lub jest usunięte)
        if (
            self.zrodlo_zrodlowe.pbn_uid_id
            and self.zrodlo_zrodlowe.pbn_uid.mniswId
            and self.zrodlo_zrodlowe.pbn_uid.status != "DELETED"
        ):
            messages.error(
                request,
                f'Źródło "{self.zrodlo_zrodlowe.nazwa}" jest na oficjalnej liście ministerstwa '
                f"(MNiSW ID: {self.zrodlo_zrodlowe.pbn_uid.mniswId}). "
                "Przemapowanie nie jest możliwe dla źródeł ministerialnych.",
            )
            return redirect("bpp:browse_zrodlo", slug=self.zrodlo_zrodlowe.slug)

        # Zlicz publikacje w źródle
        self.liczba_publikacji = Wydawnictwo_Ciagle.objects.filter(
            zrodlo=self.zrodlo_zrodlowe
        ).count()

        # Jeśli źródło nie ma publikacji, przekieruj z komunikatem
        if self.liczba_publikacji == 0:
            messages.warning(
                request,
                f'Źródło "{self.zrodlo_zrodlowe.nazwa}" nie ma żadnych publikacji. '
                "Przemapowanie nie jest możliwe.",
            )
            return redirect("bpp:browse_zrodlo", slug=self.zrodlo_zrodlowe.slug)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["zrodlo_zrodlowe"] = self.zrodlo_zrodlowe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["zrodlo_zrodlowe"] = self.zrodlo_zrodlowe
        context["liczba_publikacji"] = self.liczba_publikacji

        # Pobierz przykładowe publikacje (pierwsze 10)
        context["przykladowe_publikacje"] = Wydawnictwo_Ciagle.objects.filter(
            zrodlo=self.zrodlo_zrodlowe
        ).order_by("-rok", "tytul_oryginalny")[:10]

        return context

    def form_valid(self, form):
        zrodlo_docelowe = form.cleaned_data["zrodlo_docelowe"]

        try:
            with transaction.atomic():
                # Pobierz wszystkie publikacje do przemapowania
                publikacje = Wydawnictwo_Ciagle.objects.filter(
                    zrodlo=self.zrodlo_zrodlowe
                )

                # Zbierz historię publikacji (do JSONa)
                publikacje_historia = []
                for pub in publikacje:
                    publikacje_historia.append(
                        {
                            "id": pub.pk,
                            "tytul": pub.tytul_oryginalny,
                            "rok": pub.rok,
                        }
                    )

                # Wykonaj przemapowanie
                liczba_przemapowanych = publikacje.update(zrodlo=zrodlo_docelowe)

                # Zapisz historię przemapowania
                PrzemapowaZrodla.objects.create(
                    zrodlo_z=self.zrodlo_zrodlowe,
                    zrodlo_do=zrodlo_docelowe,
                    liczba_publikacji=liczba_przemapowanych,
                    publikacje_historia=publikacje_historia,
                    utworzono_przez=self.request.user,
                )

                messages.success(
                    self.request,
                    f"Pomyślnie przemapowano {liczba_przemapowanych} publikacji "
                    f'ze źródła "{self.zrodlo_zrodlowe.nazwa}" '
                    f'do źródła "{zrodlo_docelowe.nazwa}".',
                )

        except Exception as e:
            messages.error(
                self.request,
                f"Błąd podczas przemapowywania: {str(e)}. Operacja została cofnięta.",
            )
            return self.form_invalid(form)

        # Przekieruj do źródła docelowego
        return HttpResponseRedirect(
            reverse("bpp:browse_zrodlo", kwargs={"slug": zrodlo_docelowe.slug})
        )


class CofnijPrzemapowaView(WprowadzanieDanychRequiredMixin, View):
    """Widok do cofnięcia przemapowania źródła."""

    def post(self, request, pk):
        # Pobierz przemapowanie
        przemapowanie = get_object_or_404(PrzemapowaZrodla, pk=pk)

        # Sprawdź czy nie zostało już cofnięte
        if przemapowanie.jest_cofniete:
            messages.warning(
                request, "To przemapowanie zostało już wcześniej cofnięte."
            )
            return redirect("admin:przemapuj_zrodlo_przemapowazrodla_changelist")

        try:
            with transaction.atomic():
                # Pobierz IDs publikacji z historii
                publikacje_ids = [p["id"] for p in przemapowanie.publikacje_historia]

                # Cofnij przemapowanie: zmień z powrotem źródło
                liczba_cofnietych = Wydawnictwo_Ciagle.objects.filter(
                    pk__in=publikacje_ids, zrodlo=przemapowanie.zrodlo_do
                ).update(zrodlo=przemapowanie.zrodlo_z)

                # Oznacz przemapowanie jako cofnięte
                przemapowanie.cofnieto = timezone.now()
                przemapowanie.cofnieto_przez = request.user
                przemapowanie.save()

                if liczba_cofnietych < len(publikacje_ids):
                    messages.warning(
                        request,
                        f"Cofnięto {liczba_cofnietych} z {len(publikacje_ids)} publikacji. "
                        f"Część publikacji mogła być usunięta lub ponownie przemapowana.",
                    )
                else:
                    messages.success(
                        request,
                        f"Pomyślnie cofnięto przemapowanie. "
                        f'Przywrócono {liczba_cofnietych} publikacji do źródła "{przemapowanie.zrodlo_z.nazwa}".',
                    )

        except Exception as e:
            messages.error(request, f"Błąd podczas cofania przemapowania: {str(e)}")

        return redirect("admin:przemapuj_zrodlo_przemapowazrodla_changelist")
