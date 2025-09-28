from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from ewaluacja_metryki.models import MetrykaAutora
from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji
from .forms import OptymalizacjaForm
from .models import OptymalizacjaPublikacji

from django.contrib.auth.mixins import LoginRequiredMixin

from bpp.models import Autor_Dyscyplina, Cache_Punktacja_Autora_Query, Rekord
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
                if autor_dyscyplina.rodzaj_autora != "N":
                    continue

                dyscyplina = autor_assignment.dyscyplina_naukowa
                przypieta = autor_assignment.przypieta

                # Look up cache data if discipline is pinned
                cache_key = (autor.id, dyscyplina.id)
                cpaq = cache_punktacja_lookup.get(cache_key)

                autor_info = {
                    "autor": autor,
                    "dyscyplina": dyscyplina,
                    "jednostka": autor_assignment.jednostka,
                    "przypieta": przypieta,
                    "rekord_id": publikacja.pk,
                    "metryka_id": MetrykaAutora.objects.get(autor_id=autor.id).pk,
                }

                # Only add points/slots data if discipline is pinned and cache exists
                if przypieta and cpaq:
                    autor_info.update(
                        {
                            "punkty": cpaq.pkdaut,
                            "sloty": cpaq.slot,
                            "cache_id": cpaq.pk,
                            "jednostka_id": cpaq.jednostka_id,
                            # Publication contribution is selected for evaluation if it has non-zero slots
                            "wybrana_do_ewaluacji": cpaq.slot and cpaq.slot > 0,
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
            cache_id = request.POST.get("cache_id")
            return self._handle_unpin(request, cache_id)
        elif "pin_discipline" in request.POST:
            autor_id = request.POST.get("autor_id")
            dyscyplina_id = request.POST.get("dyscyplina_id")
            return self._handle_pin(request, slug, autor_id, dyscyplina_id)
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

    def _handle_unpin(self, request, cache_id):
        """Handle unpinning a discipline"""
        with transaction.atomic():
            cpaq = get_object_or_404(Cache_Punktacja_Autora_Query, pk=cache_id)
            publikacja = cpaq.rekord.original

            # Find and update the actual author assignment
            updated = False
            wa = publikacja.autorzy_set.filter(
                autor=cpaq.autor, dyscyplina_naukowa=cpaq.dyscyplina
            ).first()
            if wa:
                wa.przypieta = False
                wa.save()
                updated = True

            if not updated:
                raise Exception("Nie znaleziono przypisania autora do publikacji")

            # Rebuild cache punktacja for the publication
            cacher = IPunktacjaCacher(publikacja)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

            # # Refresh cache to get updated values
            # messages.success(
            #     request,
            #     f"Odpięto dyscyplinę {cpaq.dyscyplina} dla autora {cpaq.autor}",
            # )

        # If HTMX request, render the updated content directly
        if request.headers.get("HX-Request"):
            return self.get(request, slug=cpaq.rekord.slug)

        return redirect(
            "ewaluacja_optymalizuj_publikacje:optymalizuj", slug=cpaq.rekord.slug
        )

    def _handle_pin(self, request, slug, autor_id, dyscyplina_id):
        """Handle pinning a discipline"""
        with transaction.atomic():
            publikacja = get_object_or_404(Rekord, slug=slug)

            publikacja = publikacja.original

            # Find and update the actual author assignment
            updated = False

            wa = publikacja.autorzy_set.filter(
                autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
            ).first()
            if wa:
                wa.przypieta = True
                wa.save()
                updated = True

            if not updated:
                raise Exception("Nie znaleziono przypisania autora do publikacji")

            # Rebuild cache punktacja for the publication

            cacher = IPunktacjaCacher(publikacja)
            cacher.removeEntries()  # Remove old cache entries
            cacher.rebuildEntries()  # Rebuild with new przypieta status

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

            # messages.success(
            #     request,
            #     f"Przypięto dyscyplinę {dyscyplina} dla autora {autor}",
            # )

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
