import logging

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, View

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Uczelnia, Wydawnictwo_Ciagle, Zrodlo
from bpp.util import zaloguj_polkniety_wyjatek
from pbn_api.exceptions import AlreadyEnqueuedError
from pbn_export_queue.models import PBN_Export_Queue

from .forms import PrzemapowaZrodloForm
from .models import PrzemapowaZrodla

logger = logging.getLogger(__name__)


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

        # Uwaga: dla źródeł ministerialnych (z MNiSW ID) przemapowanie jest
        # dozwolone WYŁĄCZNIE na inne źródło o TYM SAMYM MNiSW ID (deduplikacja
        # tego samego czasopisma). Ta reguła jest egzekwowana w walidacji
        # formularza (PrzemapowaZrodloForm.clean_zrodlo_docelowe), bo dopiero
        # tam znane jest źródło docelowe. Strona ładuje się zawsze.

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

        # Efektywne MNiSW ID źródła (None gdy nieministerialne / usunięte z PBN).
        # Osadzane jako data-atrybut, żeby JS mógł live-sprawdzać regułę blokady
        # (źródło ministerialne wolno przemapować tylko na to samo MNiSW ID) —
        # tą samą funkcją, którą egzekwuje walidacja formularza.
        context["src_mnisw_effective"] = PrzemapowaZrodloForm._mnisw_id(
            self.zrodlo_zrodlowe
        )

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

        # Rozwiąż uczelnię raz, poza pętlą (na multi-hosted decyduje o tym,
        # do którego PBN-a wpis zostanie wysłany).
        uczelnia = Uczelnia.objects.get_for_request(self.request)

        for pub in publikacje_do_wyslania:
            try:
                PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
                    user=self.request.user, rekord=pub, uczelnia=uczelnia
                )
                sukces_pbn += 1
            except AlreadyEnqueuedError:
                bledy_pbn.append(f"Publikacja {pub.pk} jest już w kolejce")
            except Exception as e:
                zaloguj_polkniety_wyjatek(
                    f"Dodawanie publikacji do kolejki eksportu PBN "
                    f"przy przemapowaniu źródła (rekord pk={pub.pk})",
                    logger=logger,
                )
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


class ZrodloInfoView(WprowadzanieDanychRequiredMixin, View):
    """Zwraca JSON z detalami pojedynczego źródła.

    Zasila prawy panel „Źródło docelowe" na stronie przemapowania: po zmianie
    comboboxa JS fetchuje ten endpoint i wypełnia panel tymi samymi parametrami
    co panel źródłowy (skrót, ISSN, PBN UID, MNiSW ID, liczba publikacji).

    `mnisw_effective` liczone jest przez tę samą funkcję co walidacja formularza
    (PrzemapowaZrodloForm._mnisw_id), żeby live-podpowiedź w panelu była zgodna
    z regułą blokady egzekwowaną po stronie serwera.
    """

    def get(self, request, pk):
        zrodlo = get_object_or_404(Zrodlo.objects.select_related("pbn_uid"), pk=pk)
        pbn = zrodlo.pbn_uid
        liczba_publikacji = Wydawnictwo_Ciagle.objects.filter(zrodlo=zrodlo).count()

        # Zrodlo nie ma daty utworzenia — jedyny czasowy ślad to
        # `ostatnio_zmieniony` (auto_now = ostatnia modyfikacja). Kolejność
        # utworzenia oddaje pk (mniejszy = wcześniej) i to porównuje JS.
        zmieniony = zrodlo.ostatnio_zmieniony
        ostatnio_zmieniony = (
            timezone.localtime(zmieniony).strftime("%Y-%m-%d %H:%M")
            if zmieniony
            else ""
        )

        return JsonResponse(
            {
                "bppid": zrodlo.pk,
                "nazwa": zrodlo.nazwa,
                "skrot": zrodlo.skrot,
                "issn": zrodlo.issn,
                "e_issn": zrodlo.e_issn,
                "pbn_uid_id": zrodlo.pbn_uid_id,
                "mniswId": pbn.mniswId if pbn else None,
                "pbn_status": pbn.status if pbn else None,
                "mnisw_effective": PrzemapowaZrodloForm._mnisw_id(zrodlo),
                "liczba_publikacji": liczba_publikacji,
                "ostatnio_zmieniony": ostatnio_zmieniony,
                "admin_url": reverse("admin:bpp_zrodlo_change", args=[zrodlo.pk]),
            }
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
