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
from pbn_api.exceptions import AlreadyEnqueuedError
from pbn_export_queue.models import PBN_Export_Queue

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

    def get_initial(self):
        """Ustaw wartość początkową źródła docelowego z parametru GET."""
        initial = super().get_initial()

        # Sprawdź parametr GET zrodlo_docelowe
        zrodlo_docelowe_id = self.request.GET.get("zrodlo_docelowe")
        if zrodlo_docelowe_id:
            try:
                # Spróbuj znaleźć źródło po ID (primary key)
                zrodlo = Zrodlo.objects.get(pk=int(zrodlo_docelowe_id))
                initial["zrodlo_docelowe"] = zrodlo
            except (ValueError, TypeError, Zrodlo.DoesNotExist):
                # Zignoruj nieprawidłowy parametr
                pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["zrodlo_zrodlowe"] = self.zrodlo_zrodlowe
        context["liczba_publikacji"] = self.liczba_publikacji

        # Pobierz przykładowe publikacje (pierwsze 10)
        context["przykladowe_publikacje"] = Wydawnictwo_Ciagle.objects.filter(
            zrodlo=self.zrodlo_zrodlowe
        ).order_by("-rok", "tytul_oryginalny")[:10]

        return context

    def _prepare_publikacje_historia_and_list(self, publikacje, wyslac_do_pbn):
        """Prepare publication history and list of publications to send to PBN."""
        publikacje_historia = []
        publikacje_do_wyslania = []

        for pub in publikacje:
            publikacje_historia.append(
                {
                    "id": pub.pk,
                    "tytul": pub.tytul_oryginalny,
                    "rok": pub.rok,
                }
            )
            if wyslac_do_pbn:
                publikacje_do_wyslania.append(pub)

        return publikacje_historia, publikacje_do_wyslania

    def _enqueue_publikacje_to_pbn(self, publikacje_do_wyslania):
        """Add publications to PBN export queue."""
        sukces_pbn = 0
        bledy_pbn = []

        for pub in publikacje_do_wyslania:
            try:
                PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
                    user=self.request.user, rekord=pub
                )
                sukces_pbn += 1
            except AlreadyEnqueuedError:
                bledy_pbn.append(f"Publikacja {pub.pk} jest już w kolejce")
            except Exception as e:
                bledy_pbn.append(f"Publikacja {pub.pk}: {str(e)}")

        return sukces_pbn, bledy_pbn

    def _prepare_success_message(
        self,
        liczba_przemapowanych,
        zrodlo_docelowe,
        wyslac_do_pbn,
        sukces_pbn,
        bledy_pbn,
    ):
        """Prepare success message for the user."""
        msg = (
            f"Pomyślnie przemapowano {liczba_przemapowanych} publikacji "
            f'ze źródła "{self.zrodlo_zrodlowe.nazwa}" '
            f'do źródła "{zrodlo_docelowe.nazwa}".'
        )

        if wyslac_do_pbn:
            msg += f" Dodano {sukces_pbn} publikacji do kolejki eksportu PBN."
            if bledy_pbn:
                msg += f" Wystąpiły błędy dla {len(bledy_pbn)} publikacji."

        return msg

    def form_valid(self, form):
        zrodlo_docelowe = form.cleaned_data["zrodlo_docelowe"]
        wyslac_do_pbn = form.cleaned_data.get("wyslac_do_pbn", False)

        try:
            with transaction.atomic():
                # Pobierz wszystkie publikacje do przemapowania
                publikacje = Wydawnictwo_Ciagle.objects.filter(
                    zrodlo=self.zrodlo_zrodlowe
                )

                # Zbierz historię publikacji (do JSONa) i publikacje do wysłania do PBN
                publikacje_historia, publikacje_do_wyslania = (
                    self._prepare_publikacje_historia_and_list(
                        publikacje, wyslac_do_pbn
                    )
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

                # Dodaj publikacje do kolejki PBN jeśli checkbox zaznaczony
                sukces_pbn, bledy_pbn = 0, []
                if wyslac_do_pbn:
                    sukces_pbn, bledy_pbn = self._enqueue_publikacje_to_pbn(
                        publikacje_do_wyslania
                    )

                # Przygotuj komunikat sukcesu
                msg = self._prepare_success_message(
                    liczba_przemapowanych,
                    zrodlo_docelowe,
                    wyslac_do_pbn,
                    sukces_pbn,
                    bledy_pbn,
                )
                messages.success(self.request, msg)

                # Jeśli były błędy PBN, dodaj komunikat ostrzegawczy
                if bledy_pbn:
                    messages.warning(
                        self.request,
                        f"Błędy podczas dodawania do kolejki PBN: {', '.join(bledy_pbn[:5])}"
                        + (
                            f" oraz {len(bledy_pbn) - 5} innych"
                            if len(bledy_pbn) > 5
                            else ""
                        ),
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
