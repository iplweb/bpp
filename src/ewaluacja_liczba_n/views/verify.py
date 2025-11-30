from decimal import Decimal

from braces.views import GroupRequiredMixin
from django.db.models import Count, Q
from django.views.generic import TemplateView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor_Dyscyplina
from ewaluacja_common.models import Rodzaj_Autora


class WeryfikujBazeView(GroupRequiredMixin, TemplateView):
    """Widok weryfikacji poprawności bazy danych"""

    template_name = "ewaluacja_liczba_n/weryfikuj_baze.html"
    group_required = GR_WPROWADZANIE_DANYCH

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 1. Total by rodzaj_pracownika for 2022-2025
        context["rodzaje_pracownika"] = (
            Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
            .values("rodzaj_autora")
            .annotate(liczba=Count("id"))
            .order_by("rodzaj_autora")
        )

        # Pobierz obiekty Rodzaj_Autora dla mapowania
        rodzaje_dict = {r.id: r for r in Rodzaj_Autora.objects.all()}

        for item in context["rodzaje_pracownika"]:
            if item["rodzaj_autora"] is not None:
                rodzaj_obj = rodzaje_dict.get(item["rodzaj_autora"])
                if rodzaj_obj:
                    item["nazwa"] = rodzaj_obj.nazwa
                    # Mapowanie na query_key dla kompatybilności
                    skrot_mapping = {
                        "N": "rodzaj_n",
                        "D": "rodzaj_d",
                        "B": "rodzaj_b",
                        "Z": "rodzaj_z",
                    }
                    item["query_key"] = skrot_mapping.get(
                        rodzaj_obj.skrot, "brak_danych"
                    )
                else:
                    item["nazwa"] = "brak danych"
                    item["query_key"] = "brak_danych"
            else:
                item["nazwa"] = "brak danych"
                item["query_key"] = "brak_danych"

        # Count records without rodzaj_autora (empty/missing employment type)
        # Get IDs of known rodzaj_autora types
        known_rodzaje_ids = [
            r.id for r in rodzaje_dict.values() if r.skrot in ["N", "D", "B", "Z"]
        ]

        context["bez_rodzaju_zatrudnienia"] = (
            Autor_Dyscyplina.objects.filter(
                rok__gte=2022,
                rok__lte=2025,
            )
            .exclude(rodzaj_autora__in=known_rodzaje_ids)
            .count()
        )

        # 2. Records without wymiar_etatu
        context["bez_wymiaru_etatu"] = (
            Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
            .filter(Q(wymiar_etatu__isnull=True) | Q(wymiar_etatu=0))
            .select_related("autor")
            .count()
        )

        # 3. Records with missing percentage information
        # Validation rules:
        # - procent_dyscypliny must not be NULL or 0
        # - if subdyscyplina_naukowa exists, procent_subdyscypliny must not be NULL or 0
        # - only for authors with jest_w_n=True OR licz_sloty=True
        context["bez_procent"] = (
            Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
            .filter(Q(rodzaj_autora__jest_w_n=True) | Q(rodzaj_autora__licz_sloty=True))
            .filter(
                Q(procent_dyscypliny__isnull=True)  # Missing main discipline percentage
                | Q(procent_dyscypliny=Decimal("0"))  # Or percentage is 0.0
                | (
                    # Has subdiscipline but missing or 0% percentage
                    Q(subdyscyplina_naukowa__isnull=False)
                    & (
                        Q(procent_subdyscypliny__isnull=True)
                        | Q(procent_subdyscypliny=Decimal("0"))
                    )
                )
            )
            .count()
        )

        # 4. Check if sum of percentages equals 100
        # We need to check each record individually
        # Only for authors with jest_w_n=True OR licz_sloty=True
        problematic_suma = []
        all_records = (
            Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
            .filter(Q(rodzaj_autora__jest_w_n=True) | Q(rodzaj_autora__licz_sloty=True))
            .select_related("autor", "rodzaj_autora")
        )

        for record in all_records:
            procent_d = record.procent_dyscypliny or Decimal("0")
            procent_s = record.procent_subdyscypliny or Decimal("0")
            suma = procent_d + procent_s

            # Check if sum is not 100 (allowing small rounding differences)
            # Now includes records with suma = 0% as errors
            if abs(suma - Decimal("100")) > Decimal("0.01"):
                problematic_suma.append(
                    {
                        "id": record.id,
                        "autor": str(record.autor),
                        "rok": record.rok,
                        "suma": float(suma),
                    }
                )

        context["zla_suma_procent"] = len(problematic_suma)
        context["zla_suma_procent_przykłady"] = problematic_suma[
            :5
        ]  # Show first 5 examples

        # Calculate total count of records
        context["total_count"] = sum(
            item["liczba"] for item in context["rodzaje_pracownika"]
        )

        # Calculate distinct number of authors
        context["distinct_authors_count"] = (
            Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
            .values("autor")
            .distinct()
            .count()
        )

        # Generate DjangoQL queries and admin filter URLs
        # DjangoQL needs to reference the related object now
        context["djangoql_queries"] = {
            "bez_wymiaru": (
                "rok >= 2022 and rok <= 2025 and "
                "(wymiar_etatu = None or wymiar_etatu = 0)"
            ),
            "bez_procent": (
                "rok >= 2022 and rok <= 2025 and "
                "(rodzaj_autora.jest_w_n = True or rodzaj_autora.licz_sloty = True) and "
                "(procent_dyscypliny = None or procent_dyscypliny = 0 or "
                "(subdyscyplina_naukowa != None and "
                "(procent_subdyscypliny = None or procent_subdyscypliny = 0)))"
            ),
            "rodzaj_n": 'rok >= 2022 and rok <= 2025 and rodzaj_autora.skrot = "N"',
            "rodzaj_d": 'rok >= 2022 and rok <= 2025 and rodzaj_autora.skrot = "D"',
            "rodzaj_b": 'rok >= 2022 and rok <= 2025 and rodzaj_autora.skrot = "B"',
            "rodzaj_z": 'rok >= 2022 and rok <= 2025 and rodzaj_autora.skrot = "Z"',
            "brak_danych": "rok >= 2022 and rok <= 2025 and rodzaj_autora = None",
        }

        # URL for custom filter (suma != 100%) - uses custom admin filter instead of DjangoQL
        context["zla_suma_url"] = (
            "suma_procent=nieprawidlowa&rok__gte=2022&rok__lte=2025"
        )

        return context
