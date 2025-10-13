from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from ewaluacja_metryki.models import MetrykaAutora
from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji
from .forms import OptymalizacjaForm
from .models import OptymalizacjaPublikacji

from django.contrib.auth.mixins import LoginRequiredMixin

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora_Query,
    Patent_Autor,
    Rekord,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.sloty.core import CannotAdapt, IPunktacjaCacher, ISlot


class OptymalizujPublikacjeView(LoginRequiredMixin, View):
    """Main view for optimizing a single publication"""

    template_name = "ewaluacja_optymalizuj_publikacje/optymalizuj_fixed.html"

    def get(self, request, slug=None):
        context = {}

        if slug:
            publikacja = get_object_or_404(Rekord, slug=slug)
            context["publikacja"] = publikacja

            # Get all authors from the publication's autorzy_set (includes unpinned disciplines)
            autorzy_data = []

            # Build cache punktacja lookup for efficiency
            cache_punktacja_lookup = {}
            for cpaq in Cache_Punktacja_Autora_Query.objects.filter(
                rekord=publikacja
            ).select_related("autor", "dyscyplina"):
                key = (cpaq.autor_id, cpaq.dyscyplina_id)
                cache_punktacja_lookup[key] = cpaq

            # Get all author assignments with disciplines (pinned and unpinned)
            for autor_assignment in publikacja.original.autorzy_set.exclude(
                dyscyplina_naukowa=None
            ):
                autor = autor_assignment.autor
                autor_dyscyplina = Autor_Dyscyplina.objects.get(
                    autor=autor, rok=publikacja.original.rok
                )
                if not autor_dyscyplina.rodzaj_autora.licz_sloty:
                    continue

                dyscyplina = autor_assignment.dyscyplina_naukowa
                przypieta = autor_assignment.przypieta

                # Look up cache data if discipline is pinned
                cache_key = (autor.id, dyscyplina.id)
                cpaq = cache_punktacja_lookup.get(cache_key)

                # Try to get MetrykaAutora ID - it might not exist yet
                metryka_id = None
                try:
                    metryka_autor = MetrykaAutora.objects.get(autor_id=autor.id)
                    metryka_id = metryka_autor.pk
                except MetrykaAutora.DoesNotExist:
                    # MetrykaAutora doesn't exist - metrics may be rebuilding or never built
                    pass

                autor_info = {
                    "autor": autor,
                    "dyscyplina": dyscyplina,
                    "jednostka": autor_assignment.jednostka,
                    "przypieta": przypieta,
                    "rekord_id": publikacja.pk,
                    "metryka_id": metryka_id,
                    "autor_assignment_id": autor_assignment.pk,
                    "metryka_missing": metryka_id is None,
                }

                # Only add points/slots data if discipline is pinned and cache exists
                if przypieta and cpaq:
                    autor_info.update(
                        {
                            "punkty": cpaq.pkdaut,
                            "sloty": cpaq.slot,
                            "cache_id": cpaq.pk,
                            "jednostka_id": cpaq.jednostka_id,
                            # Will be updated after we fetch MetrykaAutora
                            "wybrana_do_ewaluacji": False,
                        }
                    )
                else:
                    # Calculate potential points for unpinned discipline
                    potential_punkty = None
                    potential_sloty = None

                    if not przypieta:
                        try:
                            # Get the slot calculator for this publication
                            slot_kalkulator = ISlot(publikacja.original)

                            # Count authors with this discipline (as if it were pinned)
                            authors_with_discipline = 0
                            for wa in publikacja.original.autorzy_set.all():
                                if (
                                    wa.afiliuje
                                    and wa.jednostka.skupia_pracownikow
                                    and wa.dyscyplina_naukowa == dyscyplina
                                    and wa.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow()
                                ):
                                    authors_with_discipline += 1

                            if authors_with_discipline > 0:
                                # Get PKD (points) for this discipline
                                pkd = slot_kalkulator.punkty_pkd(dyscyplina)
                                if pkd is not None:
                                    # Calculate points per author (PKD / number of authors)
                                    potential_punkty = Decimal(pkd) / Decimal(
                                        authors_with_discipline
                                    )
                                    # Calculate slot per author (1 / number of authors)
                                    potential_sloty = 1 / Decimal(
                                        1
                                        + len(
                                            slot_kalkulator.autorzy_z_dyscypliny(
                                                dyscyplina
                                            )
                                        )
                                    )

                                    if potential_sloty is None:
                                        potential_sloty = Decimal("1") / Decimal(
                                            authors_with_discipline + 1
                                        )
                        except CannotAdapt:
                            # If we can't calculate, leave as None
                            pass

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
                try:
                    metryka = MetrykaAutora.objects.get(
                        autor=autor, dyscyplina_naukowa=dyscyplina
                    )
                    autor_info["metryka"] = {
                        "punkty_nazbierane": metryka.punkty_nazbierane,
                        "srednia_punktow": metryka.srednia_za_slot_nazbierana,
                        "sloty_wypelnione": metryka.slot_nazbierany,
                        "udzial_procentowy": metryka.procent_wykorzystania_slotow,
                    }

                    # Check if this publication is actually selected for evaluation
                    # Update wybrana_do_ewaluacji based on whether this cache entry
                    # is in the author's selected publications list
                    if przypieta and cpaq and cpaq.pk in metryka.prace_nazbierane:
                        autor_info["wybrana_do_ewaluacji"] = True

                except MetrykaAutora.DoesNotExist:
                    autor_info["metryka"] = None

                autorzy_data.append(autor_info)

            context["autorzy_data"] = autorzy_data

            # Get publication points (punkty_pk)
            context["total_punkty"] = publikacja.original.punkty_kbn or 0

            # Calculate total slots only from actual cache entries (not potential)
            total_sloty = sum(
                a["sloty"] or 0
                for a in autorzy_data
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
            return self._handle_unpin(request, autor_assignment_id)
        elif "pin_discipline" in request.POST:
            autor_assignment_id = request.POST.get("autor_assignment_id")
            return self._handle_pin(request, autor_assignment_id)
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

    def _get_autor_assignments(self, publikacja):
        """Get przypieta status from actual author assignments"""
        autor_assignments = {}

        # Check different publication types
        if hasattr(publikacja, "wydawnictwo_ciagle_autor_set"):
            for wa in publikacja.wydawnictwo_ciagle_autor_set.all():
                if wa.dyscyplina_naukowa_id:
                    autor_assignments[(wa.autor_id, wa.dyscyplina_naukowa_id)] = (
                        wa.przypieta
                    )
        elif hasattr(publikacja, "wydawnictwo_zwarte_autor_set"):
            for wa in publikacja.wydawnictwo_zwarte_autor_set.all():
                if wa.dyscyplina_naukowa_id:
                    autor_assignments[(wa.autor_id, wa.dyscyplina_naukowa_id)] = (
                        wa.przypieta
                    )
        elif hasattr(publikacja, "patent_autor_set"):
            for wa in publikacja.patent_autor_set.all():
                if wa.dyscyplina_naukowa_id:
                    autor_assignments[(wa.autor_id, wa.dyscyplina_naukowa_id)] = (
                        wa.przypieta
                    )

        return autor_assignments

    def _handle_unpin(self, request, autor_assignment_id):
        """Handle unpinning a discipline"""
        with transaction.atomic():
            # Get the autor assignment directly
            # Try to find the assignment in different publication types
            wa = None
            for model in [
                Wydawnictwo_Ciagle_Autor,
                Wydawnictwo_Zwarte_Autor,
                Patent_Autor,
            ]:
                try:
                    wa = model.objects.get(pk=autor_assignment_id)
                    break
                except model.DoesNotExist:
                    continue

            if not wa:
                raise Exception("Nie znaleziono przypisania autora do publikacji")

            publikacja = wa.rekord
            slug = publikacja.slug

            # Update przypieta status
            wa.przypieta = False
            wa.save()

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

        # If HTMX request, render the updated content directly
        if request.headers.get("HX-Request"):
            return self.get(request, slug=slug)

        return redirect("ewaluacja_optymalizuj_publikacje:optymalizuj", slug=slug)

    def _handle_pin(self, request, autor_assignment_id):
        """Handle pinning a discipline"""
        with transaction.atomic():
            # Get the autor assignment directly
            # Try to find the assignment in different publication types
            wa = None
            for model in [
                Wydawnictwo_Ciagle_Autor,
                Wydawnictwo_Zwarte_Autor,
                Patent_Autor,
            ]:
                try:
                    wa = model.objects.get(pk=autor_assignment_id)
                    break
                except model.DoesNotExist:
                    continue

            if not wa:
                raise Exception("Nie znaleziono przypisania autora do publikacji")

            publikacja = wa.rekord
            slug = publikacja.slug

            # Update przypieta status
            wa.przypieta = True
            wa.save()

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

        # If HTMX request, render the updated content directly
        if request.headers.get("HX-Request"):
            return self.get(request, slug=slug)

        return redirect("ewaluacja_optymalizuj_publikacje:optymalizuj", slug=slug)


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
