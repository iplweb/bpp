from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora_Query,
    Rekord,
)
from bpp.models.sloty.core import CannotAdapt, IPunktacjaCacher, ISlot
from ewaluacja_metryki.models import MetrykaAutora
from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

from .forms import OptymalizacjaForm
from .models import OptymalizacjaPublikacji


class OptymalizujPublikacjeView(LoginRequiredMixin, View):
    """Main view for optimizing a single publication"""

    template_name = "ewaluacja_optymalizuj_publikacje/optymalizuj_fixed.html"

    def get(self, request, slug=None):
        context = {}

        if slug:
            publikacja = get_object_or_404(Rekord, slug=slug)
            context["publikacja"] = publikacja

            # Build cache punktacja lookup
            cache_punktacja_lookup = self._build_cache_punktacja_lookup(publikacja)

            # Process all author assignments
            autorzy_data_dict = {}
            stale_data_error = False

            for autor_assignment in publikacja.original.autorzy_set.exclude(
                dyscyplina_naukowa=None
            ):
                try:
                    autor_info = self._process_autor_assignment(
                        autor_assignment, publikacja, cache_punktacja_lookup
                    )
                except TypeError:
                    # Old data format detected in metryka.prace_nazbierane
                    stale_data_error = True
                    break

                if autor_info is None:
                    continue

                # Group authors by discipline
                dyscyplina = autor_assignment.dyscyplina_naukowa
                dyscyplina_key = (dyscyplina.id, dyscyplina.nazwa, dyscyplina.kod)
                if dyscyplina_key not in autorzy_data_dict:
                    autorzy_data_dict[dyscyplina_key] = []
                autorzy_data_dict[dyscyplina_key].append(autor_info)

            if stale_data_error:
                context["stale_data_error"] = True
            else:
                # Group and sort by discipline
                autorzy_po_dyscyplinach = self._group_autorzy_by_discipline(
                    autorzy_data_dict
                )
                context["autorzy_po_dyscyplinach"] = autorzy_po_dyscyplinach

                # Get publication points
                context["total_punkty"] = publikacja.original.punkty_kbn or 0

                # Calculate total slots from pinned assignments
                all_autorzy = [
                    autor
                    for dyscyplina_group in autorzy_po_dyscyplinach
                    for autor in dyscyplina_group["autorzy"]
                ]
                total_sloty = sum(
                    a["sloty"] or 0
                    for a in all_autorzy
                    if a["przypieta"] and a["sloty"] is not None
                )
                context["total_sloty"] = total_sloty

        else:
            context["form"] = OptymalizacjaForm()

        # If it's an HTMX request, return only the content wrapper partial
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ewaluacja_optymalizuj_publikacje/partials/content_wrapper.html",
                context,
            )

        return render(request, self.template_name, context)

    def post(self, request, slug=None):
        if "unpin_discipline" in request.POST:
            autor_assignment_id = request.POST.get("autor_assignment_id")
            return self._handle_unpin(request, autor_assignment_id, slug)
        elif "pin_discipline" in request.POST:
            autor_assignment_id = request.POST.get("autor_assignment_id")
            return self._handle_pin(request, autor_assignment_id, slug)
        elif "change_discipline" in request.POST:
            autor_assignment_id = request.POST.get("autor_assignment_id")
            new_discipline_id = request.POST.get("new_discipline_id")
            return self._handle_change_discipline(
                request, autor_assignment_id, new_discipline_id, slug
            )
        else:
            # Handle form submission
            form = OptymalizacjaForm(request.POST)
            if form.is_valid():
                publikacja_slug = form.cleaned_data["publikacja_input"]
                # If HTMX request, render the new content directly
                if request.headers.get("HX-Request"):
                    return self.get(request, slug=publikacja_slug)
                return redirect(
                    "ewaluacja_optymalizuj_publikacje:optymalizuj", slug=publikacja_slug
                )
            else:
                # Show form with errors
                context = {"form": form}
                return render(request, self.template_name, context)

    def _handle_unpin(self, request, autor_assignment_id, slug):
        """Handle unpinning a discipline"""
        # Get the publikacja from the slug
        publikacja = get_object_or_404(Rekord, slug=slug)

        with transaction.atomic():
            # Get the autor assignment directly from THIS publication
            # This automatically validates that the assignment belongs to this publication
            wa = publikacja.original.autorzy_set.get(pk=autor_assignment_id)

            # Update przypieta status
            wa.przypieta = False
            wa.save()

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja.original)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja.original)

        # If HTMX request, render the updated content directly
        # Use the slug from the URL
        if request.headers.get("HX-Request"):
            return self.get(request, slug=slug)

        return redirect("ewaluacja_optymalizuj_publikacje:optymalizuj", slug=slug)

    def _handle_pin(self, request, autor_assignment_id, slug):
        """Handle pinning a discipline"""
        # Get the publikacja from the slug
        publikacja = get_object_or_404(Rekord, slug=slug)

        with transaction.atomic():
            # Get the autor assignment directly from THIS publication
            # This automatically validates that the assignment belongs to this publication
            wa = publikacja.original.autorzy_set.get(pk=autor_assignment_id)

            # Update przypieta status
            wa.przypieta = True
            wa.save()

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja.original)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja.original)

        # If HTMX request, render the updated content directly
        # Use the slug from the URL
        if request.headers.get("HX-Request"):
            return self.get(request, slug=slug)

        return redirect("ewaluacja_optymalizuj_publikacje:optymalizuj", slug=slug)

    def _handle_change_discipline(
        self, request, autor_assignment_id, new_discipline_id, slug
    ):
        """Handle changing discipline for an author assignment"""
        # Get the publikacja from the slug
        publikacja = get_object_or_404(Rekord, slug=slug)

        with transaction.atomic():
            # Get the autor assignment directly from THIS publication
            # This automatically validates that the assignment belongs to this publication
            wa = publikacja.original.autorzy_set.get(pk=autor_assignment_id)

            # Import Dyscyplina_Naukowa model
            from bpp.models import Dyscyplina_Naukowa

            # Get the new discipline
            new_discipline = get_object_or_404(Dyscyplina_Naukowa, pk=new_discipline_id)

            # Update discipline
            wa.dyscyplina_naukowa = new_discipline
            wa.save()

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja.original)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new discipline

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja.original)

        # If HTMX request, render the updated content directly
        # Use the slug from the URL
        if request.headers.get("HX-Request"):
            return self.get(request, slug=slug)

        return redirect("ewaluacja_optymalizuj_publikacje:optymalizuj", slug=slug)

    def _build_cache_punktacja_lookup(self, publikacja):
        """Build cache punktacja lookup dictionary for efficiency"""
        cache_punktacja_lookup = {}
        for cpaq in Cache_Punktacja_Autora_Query.objects.filter(
            rekord=publikacja
        ).select_related("autor", "dyscyplina"):
            key = (cpaq.autor_id, cpaq.dyscyplina_id)
            cache_punktacja_lookup[key] = cpaq
        return cache_punktacja_lookup

    def _calculate_potential_points_and_slots(self, publikacja, dyscyplina):
        """Calculate potential points and slots for unpinned discipline"""
        potential_punkty = None
        potential_sloty = None

        try:
            slot_kalkulator = ISlot(publikacja.original)
            authors_with_discipline = sum(
                1
                for wa in publikacja.original.autorzy_set.all()
                if (
                    wa.afiliuje
                    and wa.jednostka.skupia_pracownikow
                    and wa.dyscyplina_naukowa == dyscyplina
                    and wa.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow()
                )
            )

            if authors_with_discipline > 0:
                pkd = slot_kalkulator.punkty_pkd(dyscyplina)
                if pkd is not None:
                    potential_punkty = Decimal(pkd) / Decimal(authors_with_discipline)
                    autorzy_z_dyscypliny = slot_kalkulator.autorzy_z_dyscypliny(
                        dyscyplina
                    )
                    potential_sloty = 1 / Decimal(1 + len(autorzy_z_dyscypliny))

                    if potential_sloty is None:
                        potential_sloty = Decimal("1") / Decimal(
                            authors_with_discipline + 1
                        )
        except CannotAdapt:
            pass

        return potential_punkty, potential_sloty

    def _get_alternative_discipline(self, autor, rok, current_discipline):
        """Get alternative discipline for autor if they have subdyscyplina_naukowa"""
        try:
            autor_dyscyplina = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)

            # Jeśli autor ma subdyscyplinę i jest różna od obecnej, zwróć ją
            if (
                autor_dyscyplina.subdyscyplina_naukowa_id
                and autor_dyscyplina.subdyscyplina_naukowa_id != current_discipline.id
            ):
                return autor_dyscyplina.subdyscyplina_naukowa

            # Jeśli obecna dyscyplina to subdyscyplina, zwróć główną
            if (
                autor_dyscyplina.subdyscyplina_naukowa_id == current_discipline.id
                and autor_dyscyplina.dyscyplina_naukowa_id != current_discipline.id
            ):
                return autor_dyscyplina.dyscyplina_naukowa

        except Autor_Dyscyplina.DoesNotExist:
            pass

        return None

    def _check_discipline_compatible_with_source(self, publikacja, dyscyplina):
        """Check if discipline is compatible with publication source"""
        # Tylko dla Wydawnictwo_Ciagle sprawdzamy zgodność ze źródłem
        if not hasattr(publikacja.original, "zrodlo") or not publikacja.original.zrodlo:
            return True

        # Pobierz dyscypliny źródła dla roku publikacji
        from bpp.models.zrodlo import Dyscyplina_Zrodla

        dyscypliny_zrodla = Dyscyplina_Zrodla.objects.filter(
            zrodlo=publikacja.original.zrodlo, rok=publikacja.original.rok
        ).values_list("dyscyplina_id", flat=True)

        # Jeśli źródło nie ma przypisanych dyscyplin, uznajemy że wszystko jest OK
        if not dyscypliny_zrodla:
            return True

        # Sprawdź czy dyscyplina autora jest w dyscyplinach źródła
        return dyscyplina.id in list(dyscypliny_zrodla)

    def _get_metryka_data(self, autor, dyscyplina, przypieta, cpaq):
        """Get MetrykaAutora data and check if publication is selected for evaluation"""
        metryka_data = None
        wybrana_do_ewaluacji = False

        try:
            metryka = MetrykaAutora.objects.get(
                autor=autor, dyscyplina_naukowa=dyscyplina
            )
            metryka_data = {
                "punkty_nazbierane": metryka.punkty_nazbierane,
                "srednia_punktow": metryka.srednia_za_slot_nazbierana,
                "sloty_wypelnione": metryka.slot_nazbierany,
                "udzial_procentowy": metryka.procent_wykorzystania_slotow,
            }

            # JSON stores arrays, but rekord_id is a tuple - need to convert for comparison
            if (
                przypieta
                and cpaq
                and cpaq.rekord_id in [tuple(x) for x in metryka.prace_nazbierane]
            ):
                wybrana_do_ewaluacji = True

        except MetrykaAutora.DoesNotExist:
            pass

        return metryka_data, wybrana_do_ewaluacji

    def _process_autor_assignment(
        self, autor_assignment, publikacja, cache_punktacja_lookup
    ):
        """Process a single autor assignment and return autor info dict"""
        autor = autor_assignment.autor
        dyscyplina = autor_assignment.dyscyplina_naukowa
        przypieta = autor_assignment.przypieta

        # Get autor dyscyplina info
        autor_dyscyplina = Autor_Dyscyplina.objects.select_related("rodzaj_autora").get(
            autor=autor, rok=publikacja.original.rok
        )

        if not autor_dyscyplina.rodzaj_autora.licz_sloty:
            return None

        # Look up cache data if discipline is pinned
        cache_key = (autor.id, dyscyplina.id)
        cpaq = cache_punktacja_lookup.get(cache_key)

        # Try to get MetrykaAutora ID
        metryka_id = None
        try:
            metryka_autor = MetrykaAutora.objects.get(
                autor_id=autor.id, dyscyplina_naukowa=dyscyplina
            )
            metryka_id = metryka_autor.pk
        except MetrykaAutora.DoesNotExist:
            pass

        # Check if autor_dyscyplina has required fields filled
        autor_dyscyplina_missing_data = False
        # Sprawdź czy autor ma wpis w IloscUdzialowDlaAutoraZaCalosc
        has_ilosc_udzialow = False
        if metryka_id is None:
            from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

            has_ilosc_udzialow = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                autor=autor, dyscyplina_naukowa=dyscyplina
            ).exists()

            autor_dyscyplina_missing_data = (
                autor_dyscyplina.procent_dyscypliny is None
                or autor_dyscyplina.wymiar_etatu is None
                or not has_ilosc_udzialow
            )

        autor_info = {
            "autor": autor,
            "dyscyplina": dyscyplina,
            "jednostka": autor_assignment.jednostka,
            "przypieta": przypieta,
            "rekord_id": publikacja.pk,
            "metryka_id": metryka_id,
            "autor_assignment_id": autor_assignment.pk,
            "metryka_missing": metryka_id is None,
            "rodzaj_autora": autor_dyscyplina.rodzaj_autora,
            "autor_dyscyplina_id": autor_dyscyplina.pk,
            "autor_dyscyplina_missing_data": autor_dyscyplina_missing_data,
        }

        # Add points/slots data based on whether discipline is pinned
        if przypieta and cpaq:
            autor_info.update(
                {
                    "punkty": cpaq.pkdaut,
                    "sloty": cpaq.slot,
                    "cache_id": cpaq.pk,
                    "jednostka_id": cpaq.jednostka_id,
                    "wybrana_do_ewaluacji": False,
                }
            )
        else:
            potential_punkty, potential_sloty = (
                self._calculate_potential_points_and_slots(publikacja, dyscyplina)
                if not przypieta
                else (None, None)
            )
            autor_info.update(
                {
                    "punkty": potential_punkty,
                    "sloty": potential_sloty,
                    "cache_id": None,
                    "jednostka_id": autor_assignment.jednostka_id,
                    "wybrana_do_ewaluacji": False,
                }
            )

        # Get MetrykaAutora data
        metryka_data, wybrana_do_ewaluacji = self._get_metryka_data(
            autor, dyscyplina, przypieta, cpaq
        )
        autor_info["metryka"] = metryka_data
        if wybrana_do_ewaluacji:
            autor_info["wybrana_do_ewaluacji"] = True

        # Get alternative discipline (subdyscyplina)
        alternative_discipline = self._get_alternative_discipline(
            autor, publikacja.original.rok, dyscyplina
        )
        if alternative_discipline:
            autor_info["alternative_discipline"] = {
                "id": alternative_discipline.id,
                "nazwa": alternative_discipline.nazwa,
                "kod": alternative_discipline.kod,
            }
            # Check if alternative discipline is compatible with source
            autor_info["alternative_discipline_compatible"] = (
                self._check_discipline_compatible_with_source(
                    publikacja, alternative_discipline
                )
            )

        # Check if current discipline is compatible with source
        autor_info["discipline_compatible"] = (
            self._check_discipline_compatible_with_source(publikacja, dyscyplina)
        )

        return autor_info

    def _group_autorzy_by_discipline(self, autorzy_data_dict):
        """Convert dict to list sorted by discipline name"""
        return [
            {
                "dyscyplina": {"id": dyscyplina_id, "nazwa": nazwa, "kod": kod},
                "autorzy": autorzy,
            }
            for (dyscyplina_id, nazwa, kod), autorzy in sorted(
                autorzy_data_dict.items(), key=lambda x: x[0][1]
            )
        ]


class HistoriaOptymalizacjiView(LoginRequiredMixin, View):
    """View optimization history"""

    template_name = "ewaluacja_optymalizuj_publikacje/historia.html"

    def get(self, request, slug):
        publikacja = get_object_or_404(Rekord, slug=slug)
        optymalizacje = OptymalizacjaPublikacji.objects.filter(
            publikacja_id=publikacja.pk
        ).prefetch_related("historia_zmian")

        context = {"publikacja": publikacja, "optymalizacje": optymalizacje}

        return render(request, self.template_name, context)
