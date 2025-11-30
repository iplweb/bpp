from django.db.models import Avg, Count, Q
from django.views.generic import ListView

from bpp.models import Jednostka, Wydzial
from bpp.models.uczelnia import Uczelnia
from ewaluacja_common.models import Rodzaj_Autora

from ..models import MetrykaAutora, StatusGenerowania
from .mixins import EwaluacjaRequiredMixin


class MetrykiListView(EwaluacjaRequiredMixin, ListView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/lista.html"
    context_object_name = "metryki"
    paginate_by = 20

    def get_paginate_by(self, queryset):
        """Wyłącz paginację dla widoków kółek, metryki i wykresów"""
        widok = self.request.GET.get("widok", "tabela")
        if widok in [
            "kola",
            "pkdaut",
            "mapa_ciepla",
            "mapa_ciepla_bloki",
            "mapa_konturowa",
            "wykres_babelkowy",
            "kontury_z_punktami",
            "efektywnosc_babelki",
            "efektywnosc_mapa_ciepla",
            "przestrzen_pasternaka",  # Wykres 3D: X=sloty, Y=punkty, Z=średni IF
            "kosmos_bpp_3d",  # Wykres 3D: X=sloty, Y=punkty, Z=średni rok prac
        ]:
            return None  # Disable pagination for visualization views
        return self.paginate_by

    def _apply_filters(self, queryset):
        """Apply all filter parameters from GET request to queryset."""
        # Filtrowanie po ID autora (dla przycisku "Kadruj")
        autor_id = self.request.GET.get("autor_id")
        if autor_id:
            queryset = queryset.filter(autor_id=autor_id)

        # Filtrowanie po nazwisku
        nazwisko = self.request.GET.get("nazwisko")
        if nazwisko:
            queryset = queryset.filter(
                Q(autor__nazwisko__icontains=nazwisko)
                | Q(autor__imiona__icontains=nazwisko)
            )

        # Filtrowanie po jednostce
        jednostka_id = self.request.GET.get("jednostka")
        if jednostka_id:
            queryset = queryset.filter(jednostka_id=jednostka_id)

        # Filtrowanie po wydziale
        wydzial_id = self.request.GET.get("wydzial")
        if wydzial_id:
            queryset = queryset.filter(jednostka__wydzial_id=wydzial_id)

        # Filtrowanie po dyscyplinie
        dyscyplina_id = self.request.GET.get("dyscyplina")
        if dyscyplina_id:
            queryset = queryset.filter(dyscyplina_naukowa_id=dyscyplina_id)

        # Filtrowanie po rodzaju autora
        rodzaj_autora = self.request.GET.get("rodzaj_autora")
        if rodzaj_autora and rodzaj_autora != "":
            queryset = queryset.filter(rodzaj_autora=rodzaj_autora)

        return queryset

    def _apply_sorting(self, queryset):
        """Apply sorting based on sort parameter."""
        sort = self.request.GET.get("sort", "-srednia_za_slot_nazbierana")
        allowed_sorts = [
            "srednia_za_slot_nazbierana",
            "-srednia_za_slot_nazbierana",
            "procent_wykorzystania_slotow",
            "-procent_wykorzystania_slotow",
            "autor__nazwisko",
            "-autor__nazwisko",
        ]

        if sort not in allowed_sorts:
            return queryset

        # Define sorting with secondary sort column
        sort_mapping = {
            "procent_wykorzystania_slotow": (
                "procent_wykorzystania_slotow",
                "srednia_za_slot_nazbierana",
            ),
            "-procent_wykorzystania_slotow": (
                "-procent_wykorzystania_slotow",
                "-srednia_za_slot_nazbierana",
            ),
            "srednia_za_slot_nazbierana": (
                "srednia_za_slot_nazbierana",
                "procent_wykorzystania_slotow",
            ),
            "-srednia_za_slot_nazbierana": (
                "-srednia_za_slot_nazbierana",
                "-procent_wykorzystania_slotow",
            ),
        }

        if sort in sort_mapping:
            return queryset.order_by(*sort_mapping[sort])
        return queryset.order_by(sort)

    def get_queryset(self):
        from django.db.models import Count, OuterRef, Subquery

        # Subquery to count disciplines for each author
        discipline_count = (
            MetrykaAutora.objects.filter(autor=OuterRef("autor"))
            .values("autor")
            .annotate(count=Count("dyscyplina_naukowa"))
            .values("count")
        )

        queryset = (
            super()
            .get_queryset()
            .select_related(
                "autor", "dyscyplina_naukowa", "jednostka", "jednostka__wydzial"
            )
            .annotate(autor_discipline_count=Subquery(discipline_count))
        )

        queryset = self._apply_filters(queryset)
        queryset = self._apply_sorting(queryset)

        return queryset

    def _get_filtered_autor_context(self):
        """Get filtered autor information if autor_id is in request."""
        autor_id = self.request.GET.get("autor_id")
        if not autor_id:
            return {}

        from bpp.models import Autor

        try:
            autor = Autor.objects.get(pk=autor_id)
            return {"filtered_autor": autor}
        except Autor.DoesNotExist:
            return {}

    def _get_jednostki_wydzialy_context(self):
        """Get jednostki and wydzialy lists for filters."""
        from bpp.models import Autor

        context = {}

        # Sprawdź czy uczelnia używa wydziałów
        uczelnia = Uczelnia.objects.get_default()
        context["uzywa_wydzialow"] = uczelnia.uzywaj_wydzialow if uczelnia else False

        # Jeśli wydzial jest wybrany, filtruj jednostki tylko z tego wydziału
        wydzial_id = self.request.GET.get("wydzial")
        jednostki_queryset = Jednostka.objects.filter(
            pk__in=Autor.objects.filter(metryki__isnull=False)
            .values_list("aktualna_jednostka", flat=True)
            .distinct()
        ).distinct()

        if wydzial_id:
            jednostki_queryset = jednostki_queryset.filter(wydzial_id=wydzial_id)

        context["jednostki"] = jednostki_queryset.order_by("nazwa")

        if context["uzywa_wydzialow"]:
            # Buduj listę wydziałów na podstawie aktualnych jednostek autorów z metrykami
            context["wydzialy"] = (
                Wydzial.objects.filter(
                    jednostka__in=Autor.objects.filter(metryki__isnull=False)
                    .values_list("aktualna_jednostka", flat=True)
                    .distinct()
                )
                .distinct()
                .order_by("nazwa")
            )
            # Check if there's only one faculty
            context["tylko_jeden_wydzial"] = context["wydzialy"].count() == 1
        else:
            context["tylko_jeden_wydzial"] = False

        return context

    def _get_dyscypliny_context(self):
        """Get dyscypliny list for filters."""
        from bpp.models import Dyscyplina_Naukowa

        dyscypliny = (
            Dyscyplina_Naukowa.objects.filter(metrykaautora__isnull=False)
            .distinct()
            .order_by("nazwa")
        )

        return {
            "dyscypliny": dyscypliny,
            "tylko_jedna_dyscyplina": dyscypliny.count() == 1,
        }

    def _get_statistics_context(self):
        """Get statistics for current queryset."""
        stats = self.get_queryset().aggregate(
            srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
            srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
            liczba_wierszy=Count("id"),
            liczba_autorow=Count("autor", distinct=True),
        )
        return {"statystyki": stats}

    def _get_status_context(self):
        """Get generation status and progress information."""
        status = StatusGenerowania.get_or_create()
        context = {
            "status_generowania": status,
            "dostepne_rodzaje_autorow": Rodzaj_Autora.objects.filter(
                licz_sloty=True
            ).order_by("sort"),
        }

        # Oblicz procent postępu
        if status.w_trakcie and status.liczba_do_przetworzenia > 0:
            context["progress_procent"] = round(
                (status.liczba_przetworzonych / status.liczba_do_przetworzenia * 100), 1
            )
        else:
            context["progress_procent"] = 0

        return context

    def _calculate_3d_metrics(self, metryki, widok):
        """Calculate average IF and average year for 3D visualizations."""
        if widok not in ["przestrzen_pasternaka", "kosmos_bpp_3d"]:
            return

        from bpp.models.cache import Cache_Punktacja_Autora_Query

        # Iterate through all metryki and calculate average IF and average year
        for metryka in metryki:
            # Get all works for this author/discipline
            if metryka.prace_nazbierane:
                # Query by stable rekord_id
                prace = Cache_Punktacja_Autora_Query.objects.filter(
                    rekord_id__in=metryka.prace_nazbierane,
                    autor_id=metryka.autor_id,
                    dyscyplina_id=metryka.dyscyplina_naukowa_id,
                ).select_related("rekord")

                # Calculate average Impact Factor
                impact_factors = []
                years = []
                for praca in prace:
                    years.append(praca.rekord.rok)
                    try:
                        if hasattr(praca.rekord, "original") and hasattr(
                            praca.rekord.original, "impact_factor"
                        ):
                            if praca.rekord.original.impact_factor:
                                impact_factors.append(
                                    float(praca.rekord.original.impact_factor)
                                )
                    except (AttributeError, ValueError, TypeError):
                        pass

                # Set average IF (or 0 if no IF data)
                metryka.sredni_if = (
                    sum(impact_factors) / len(impact_factors) if impact_factors else 0.0
                )

                # Set average year
                metryka.sredni_rok = (
                    sum(years) / len(years) if years else metryka.rok_min
                )
            else:
                metryka.sredni_if = 0.0
                metryka.sredni_rok = metryka.rok_min

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Set default widok to "tabela" if not provided
        context["widok"] = self.request.GET.get("widok", "tabela")

        # Zachowaj parametry filtru
        context["request"] = self.request

        # Update context with data from helper methods
        context.update(self._get_filtered_autor_context())
        context.update(self._get_jednostki_wydzialy_context())
        context.update(self._get_dyscypliny_context())
        context.update(self._get_statistics_context())
        context.update(self._get_status_context())

        # Calculate 3D metrics if needed
        self._calculate_3d_metrics(context.get("metryki", []), context["widok"])

        return context
