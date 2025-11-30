from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import DetailView

from ewaluacja_common.models import Rodzaj_Autora

from ..models import MetrykaAutora
from .mixins import EwaluacjaRequiredMixin


class MetrykaDetailView(EwaluacjaRequiredMixin, DetailView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/szczegoly.html"
    context_object_name = "metryka"

    def get_object(self, queryset=None):
        """Override get_object to lookup by autor slug and dyscyplina kod"""
        if queryset is None:
            queryset = self.get_queryset()

        autor_slug = self.kwargs.get("autor_slug")
        dyscyplina_kod = self.kwargs.get("dyscyplina_kod")

        if not autor_slug or not dyscyplina_kod:
            from django.http import Http404

            raise Http404("Autor slug and dyscyplina kod are required")

        try:
            obj = queryset.get(
                autor__slug=autor_slug, dyscyplina_naukowa__kod=dyscyplina_kod
            )
        except self.model.DoesNotExist as err:
            from django.http import Http404

            raise Http404(
                f"MetrykaAutora for autor '{autor_slug}' and dyscyplina '{dyscyplina_kod}' not found"
            ) from err

        return obj

    def get(self, request, *args, **kwargs):
        """Override get to handle missing metrics gracefully"""
        from django.http import Http404

        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # Redirect to main list with error message instead of showing 404 page
            messages.error(
                request,
                "Nie znaleziono metryki ewaluacyjnej dla tego autora i dyscypliny. "
                "Proszę o wygenerowanie metryk ponownie.",
            )
            return redirect("ewaluacja_metryki:lista")

    def _get_discipline_years_context(self, metryka):
        """Get discipline years and calculate averages."""
        from decimal import Decimal

        from bpp.models import Autor_Dyscyplina

        context = {}

        dyscyplina_lata = (
            Autor_Dyscyplina.objects.filter(
                autor=metryka.autor,
                dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                rok__in=[2022, 2023, 2024, 2025],
            )
            .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
            .order_by("rok")
        )
        context["dyscyplina_lata"] = dyscyplina_lata

        if dyscyplina_lata:
            suma_etatu = Decimal("0")
            liczba_etatu = 0
            suma_procent = Decimal("0")
            liczba_procent = 0

            for rok_data in dyscyplina_lata:
                if rok_data.wymiar_etatu:
                    suma_etatu += rok_data.wymiar_etatu
                    liczba_etatu += 1

                # Sprawdź czy to subdyscyplina czy dyscyplina główna
                if (
                    rok_data.subdyscyplina_naukowa
                    and rok_data.subdyscyplina_naukowa == metryka.dyscyplina_naukowa
                ):
                    if rok_data.procent_subdyscypliny:
                        suma_procent += rok_data.procent_subdyscypliny
                        liczba_procent += 1
                else:
                    if rok_data.procent_dyscypliny:
                        suma_procent += rok_data.procent_dyscypliny
                        liczba_procent += 1

            context["srednia_etatu"] = (
                (suma_etatu / liczba_etatu) if liczba_etatu > 0 else None
            )
            context["srednia_procent"] = (
                (suma_procent / liczba_procent) if liczba_procent > 0 else None
            )

        return context

    def _get_collected_works_context(self, metryka):
        """Get collected works (nazbierane) with pkdaut/slot calculations."""
        from bpp.models.cache import Cache_Punktacja_Autora_Query

        context = {}

        if metryka.prace_nazbierane:
            # Convert JSON lists to tuples for PostgreSQL tuple matching
            # JSONField stores tuples as lists: (51, 123) -> [51, 123]

            # Query by stable rekord_id (survives cache rebuilds from pin/unpin)
            prace_nazbierane = (
                Cache_Punktacja_Autora_Query.objects.filter(
                    rekord_id__in=metryka.prace_nazbierane,
                    autor_id=metryka.autor_id,
                    dyscyplina_id=metryka.dyscyplina_naukowa_id,
                )
                .select_related("rekord")
                .order_by("-pkdaut")
            )

            # Calculate pkdaut/slot for each work and set URL parameters
            for praca in prace_nazbierane:
                if praca.slot and praca.slot > 0:
                    praca.pkdaut_per_slot = float(praca.pkdaut) / float(praca.slot)
                else:
                    praca.pkdaut_per_slot = None

                # Set URL parameters for pin/unpin actions
                praca.rekord_content_type_id = praca.rekord.id[0]
                praca.rekord_object_id = praca.rekord.id[1]
                praca.autor_id = metryka.autor.id
                praca.dyscyplina_id = metryka.dyscyplina_naukowa.id

            context["prace_nazbierane"] = prace_nazbierane

        context["liczba_prac_nazbierane"] = (
            len(metryka.prace_nazbierane) if metryka.prace_nazbierane else 0
        )

        return context

    def _get_chart_data_context(self, metryka):
        """Prepare data for visualization charts."""
        import json
        from collections import defaultdict

        from bpp.models.cache import Cache_Punktacja_Autora_Query

        context = {}

        # Pobierz wszystkie prace (nazbierane i nie nazbierane) z latami
        if metryka.prace_wszystkie:
            # Convert JSON lists to tuples for PostgreSQL tuple matching

            # Query by stable rekord_id
            prace_wszystkie = (
                Cache_Punktacja_Autora_Query.objects.filter(
                    rekord_id__in=metryka.prace_wszystkie,
                    autor_id=metryka.autor_id,
                    dyscyplina_id=metryka.dyscyplina_naukowa_id,
                )
                .select_related("rekord")
                .order_by("rekord__rok", "-pkdaut")
            )

            # Build set of rekord_ids from nazbierane works
            # JSONField stores tuples as lists: (51, 123) -> [51, 123] - convert back to tuples for hashing
            nazbierane_set = (
                {tuple(x) for x in metryka.prace_nazbierane}
                if metryka.prace_nazbierane
                else set()
            )

            # Przygotuj dane dla wykresów
            chart_data = []
            year_aggregates = defaultdict(
                lambda: {"punkty": 0, "sloty": 0, "liczba": 0}
            )

            for praca in prace_wszystkie:
                rok = praca.rekord.rok
                pkdaut = float(praca.pkdaut or 0)
                slot = float(praca.slot or 0)
                # Check if work is in nazbierane set using stable rekord_id tuple
                is_nazbierana = tuple(praca.rekord_id) in nazbierane_set

                # Get Impact Factor from original publication if available
                impact_factor = 0.0
                try:
                    if hasattr(praca.rekord, "original") and hasattr(
                        praca.rekord.original, "impact_factor"
                    ):
                        if praca.rekord.original.impact_factor:
                            impact_factor = float(praca.rekord.original.impact_factor)
                except (AttributeError, ValueError, TypeError):
                    pass

                chart_data.append(
                    {
                        "rok": rok,
                        "pkdaut": pkdaut,
                        "slot": slot,
                        "tytul": str(praca.rekord.tytul_oryginalny or ""),
                        "is_nazbierana": is_nazbierana,
                        "impact_factor": impact_factor,
                    }
                )

                year_aggregates[rok]["punkty"] += pkdaut
                year_aggregates[rok]["sloty"] += slot
                year_aggregates[rok]["liczba"] += 1

            # Serializuj do JSON
            context["chart_data_json"] = json.dumps(chart_data)
            context["year_aggregates_json"] = json.dumps(dict(year_aggregates))
            context["chart_data"] = chart_data  # Keep for template conditional

        return context

    def _get_all_works_context(self, metryka):
        """Get all works (wszystkie) with pkdaut/slot calculations."""
        from bpp.models.cache import Cache_Punktacja_Autora_Query

        context = {}

        if metryka.prace_wszystkie:
            # Convert JSON lists to tuples for PostgreSQL tuple matching
            # Query by stable rekord_id (survives cache rebuilds)
            prace_wszystkie = (
                Cache_Punktacja_Autora_Query.objects.filter(
                    rekord_id__in=metryka.prace_wszystkie,
                    autor_id=metryka.autor_id,
                    dyscyplina_id=metryka.dyscyplina_naukowa_id,
                )
                .select_related("rekord")
                .order_by("-pkdaut")
            )

            # Calculate pkdaut/slot for each work and set URL parameters
            for praca in prace_wszystkie:
                if praca.slot and praca.slot > 0:
                    praca.pkdaut_per_slot = float(praca.pkdaut) / float(praca.slot)
                else:
                    praca.pkdaut_per_slot = None

                # Mark if this work is in nazbierane set (for template highlighting)
                praca.is_nazbierana = praca.rekord_id in [
                    tuple(x) for x in metryka.prace_nazbierane
                ]

                # Set URL parameters for pin/unpin actions
                praca.rekord_content_type_id = praca.rekord.id[0]
                praca.rekord_object_id = praca.rekord.id[1]
                praca.autor_id = metryka.autor.id
                praca.dyscyplina_id = metryka.dyscyplina_naukowa.id

            context["prace_wszystkie"] = prace_wszystkie

        return context

    def _get_unpinned_works_context(self, metryka):
        """Get unpinned works (odpiete) from all publication models."""
        from decimal import Decimal

        from django.contrib.contenttypes.models import ContentType

        from bpp.models import (
            Patent_Autor,
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
        )

        context = {}
        prace_odpiete = []

        # Query all three types of unpinned publications
        for model in [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor]:
            assignments = model.objects.filter(
                autor=metryka.autor,
                dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                przypieta=False,
                rekord__rok__gte=metryka.rok_min,
                rekord__rok__lte=metryka.rok_max,
            ).select_related("rekord")

            for assignment in assignments:
                rekord = assignment.rekord
                author_count = Decimal(str(rekord.autorzy_set.count() or 1))

                # Get content type and object id for URL parameters
                content_type = ContentType.objects.get_for_model(rekord)

                praca = type(
                    "PracaOdpieta",
                    (),
                    {
                        "rekord": rekord,
                        "tytul_oryginalny": rekord.tytul_oryginalny,
                        "rok": rekord.rok,
                        "pkdaut_est": Decimal(str(rekord.punkty_kbn or 0))
                        / author_count,
                        "slot_est": Decimal("1") / author_count,
                        "rekord_content_type_id": content_type.pk,
                        "rekord_object_id": rekord.pk,
                        "autor_id": metryka.autor.id,
                        "dyscyplina_id": metryka.dyscyplina_naukowa.id,
                    },
                )()

                # Calculate estimated PKDaut/slot
                if praca.slot_est and praca.slot_est > 0:
                    praca.pkdaut_per_slot_est = float(praca.pkdaut_est) / float(
                        praca.slot_est
                    )
                else:
                    praca.pkdaut_per_slot_est = None

                prace_odpiete.append(praca)

        # Sort by estimated PKDaut descending
        prace_odpiete.sort(key=lambda x: x.pkdaut_est, reverse=True)

        # Add to context if there are unpinned works
        if prace_odpiete:
            context["prace_odpiete"] = prace_odpiete
            context["prace_odpiete_suma_pkdaut"] = sum(
                p.pkdaut_est for p in prace_odpiete
            )
            context["prace_odpiete_suma_slotow"] = sum(
                p.slot_est for p in prace_odpiete
            )
            context["prace_odpiete_liczba"] = len(prace_odpiete)

        return context

    def _get_position_context(self, metryka):
        """Get author's position in unit rankings."""
        context = {}

        if metryka.jednostka:
            context["pozycja_w_jednostce"] = (
                MetrykaAutora.objects.filter(
                    jednostka=metryka.jednostka,
                    dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                    srednia_za_slot_nazbierana__gt=metryka.srednia_za_slot_nazbierana,
                ).count()
                + 1
            )

            context["liczba_w_jednostce"] = MetrykaAutora.objects.filter(
                jednostka=metryka.jednostka,
                dyscyplina_naukowa=metryka.dyscyplina_naukowa,
            ).count()

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        metryka = self.object

        # Pobierz inne dyscypliny tego samego autora
        inne_dyscypliny = (
            MetrykaAutora.objects.filter(autor=metryka.autor)
            .exclude(pk=metryka.pk)
            .select_related("dyscyplina_naukowa")
            .order_by("dyscyplina_naukowa__nazwa")
        )
        context["inne_dyscypliny"] = inne_dyscypliny

        # Dodaj dostępne rodzaje autorów dla szablonu
        context["rodzaje_autorow"] = Rodzaj_Autora.objects.all().order_by("skrot")

        # Get all context data from helper methods
        context.update(self._get_discipline_years_context(metryka))
        context.update(self._get_collected_works_context(metryka))
        context.update(self._get_all_works_context(metryka))
        context.update(self._get_unpinned_works_context(metryka))
        context.update(self._get_position_context(metryka))
        context.update(self._get_chart_data_context(metryka))

        return context
