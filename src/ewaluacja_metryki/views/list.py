from django.db.models import Avg, Count, Q
from django.views.generic import ListView

from bpp.models import Jednostka
from ewaluacja_common.models import Rodzaj_Autora
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

from ..models import MetrykaAutora, StatusGenerowania
from ..uczelnia_scope import scope_metryki
from .mixins import EwaluacjaRequiredMixin, ma_pelne_uprawnienia_ewaluacji


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

    def _is_autor_only(self):
        """Czy użytkownik ma dostęp tylko do swoich metryk."""
        return not ma_pelne_uprawnienia_ewaluacji(self.request.user)

    def _apply_filters(self, queryset):
        """Apply all filter parameters from GET request to queryset."""
        # Dla użytkowników autor-only: wymuszaj filtrowanie
        # po ich własnym autorze
        if self._is_autor_only():
            queryset = queryset.filter(autor_id=self.request.user.autor_id)
        else:
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
            # Faza B (#438): „wydział" = jednostka-korzeń (self-FK). Poddrzewo
            # łapie ``jednostka__wydzial_id``; metryki autorów przy SAMYM
            # korzeniu (``wydzial=NULL``) — ``jednostka_id`` (bez tego znikają).
            queryset = queryset.filter(
                Q(jednostka__wydzial_id=wydzial_id) | Q(jednostka_id=wydzial_id)
            )

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

        # Subquery to count disciplines for each author within their own uczelnia
        discipline_count = (
            MetrykaAutora.objects.filter(
                autor=OuterRef("autor"),
                uczelnia=OuterRef("uczelnia"),
            )
            .values("autor")
            .annotate(count=Count("dyscyplina_naukowa"))
            .values("count")
        )

        uczelnia = uczelnia_dla_odczytu(self.request)
        queryset = scope_metryki(
            super()
            .get_queryset()
            .select_related(
                "autor",
                "dyscyplina_naukowa",
                "jednostka",
                "jednostka__wydzial",
            )
            .annotate(autor_discipline_count=Subquery(discipline_count)),
            uczelnia,
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

        # Sprawdź czy uczelnia używa wydziałów (scope per oglądanej uczelni)
        uczelnia = uczelnia_dla_odczytu(self.request)
        context["uzywa_wydzialow"] = uczelnia.uzywaj_wydzialow if uczelnia else False

        # Autorzy mający metryki w bieżącej uczelni (scoped)
        scoped_metryki_autorzy = (
            scope_metryki(MetrykaAutora.objects.all(), uczelnia)
            .values_list("autor_id", flat=True)
            .distinct()
        )

        # Jeśli wydzial jest wybrany, filtruj jednostki tylko z tego wydziału
        wydzial_id = self.request.GET.get("wydzial")
        jednostki_queryset = Jednostka.objects.filter(
            pk__in=Autor.objects.filter(
                pk__in=scoped_metryki_autorzy,
            )
            .values_list("aktualna_jednostka", flat=True)
            .distinct()
        ).distinct()

        if wydzial_id:
            # Poddrzewo wydziału (``wydzial_id``) + SAM korzeń (``pk``): korzeń
            # ma ``wydzial=NULL``, więc bez ``| Q(pk=…)`` jednostki-roota nie
            # dałoby się wybrać z listy.
            jednostki_queryset = jednostki_queryset.filter(
                Q(wydzial_id=wydzial_id) | Q(pk=wydzial_id)
            )

        context["jednostki"] = jednostki_queryset.order_by("nazwa")

        if context["uzywa_wydzialow"]:
            # Faza B (#438): „wydziały" = jednostki-korzenie. Dawny
            # ``Wydzial.objects.filter(jednostka__in=…)`` (reverse-rel po FK→
            # Wydzial) po retargecie znika (FieldError). Budujemy listę
            # korzeni z pola ``wydzial`` (self-FK) aktualnych jednostek autorów.
            aktualne_jednostki_ids = (
                Autor.objects.filter(pk__in=scoped_metryki_autorzy)
                .values_list("aktualna_jednostka", flat=True)
                .distinct()
            )
            # „Wydział" aktualnej jednostki = jej denorm. ``wydzial`` (korzeń);
            # dla jednostki będącej SAMYM korzeniem (``wydzial_id=NULL``) —
            # jej WŁASNE pk. Bez tego wydziały, w których autorzy siedzą wprost
            # na roocie, znikały z filtra (i mogły błędnie zapalić
            # ``tylko_jeden_wydzial`` → ukrycie całego filtra).
            root_ids = {
                wydzial_id if wydzial_id is not None else pk
                for pk, wydzial_id in Jednostka.objects.filter(
                    pk__in=aktualne_jednostki_ids
                ).values_list("pk", "wydzial_id")
            }
            context["wydzialy"] = Jednostka.objects.filter(pk__in=root_ids).order_by(
                "nazwa"
            )
            # Check if there's only one faculty
            context["tylko_jeden_wydzial"] = context["wydzialy"].count() == 1
        else:
            context["tylko_jeden_wydzial"] = False

        return context

    def _get_dyscypliny_context(self):
        """Get dyscypliny list for filters."""
        from bpp.models import Dyscyplina_Naukowa

        uczelnia = uczelnia_dla_odczytu(self.request)
        scoped_dyscypliny_ids = (
            scope_metryki(MetrykaAutora.objects.all(), uczelnia)
            .values_list("dyscyplina_naukowa_id", flat=True)
            .distinct()
        )
        dyscypliny = (
            Dyscyplina_Naukowa.objects.filter(pk__in=scoped_dyscypliny_ids)
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
        uczelnia = uczelnia_dla_odczytu(self.request)
        status = StatusGenerowania.get_or_create(uczelnia=uczelnia)
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
                # read-side multi-uczelnia: zawężone transitive po autor_id+dyscyplina_id;
                # rewizja per-uczelnia metryk należy do federacji, nie R1.
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

        autor_only_mode = self._is_autor_only()
        context["autor_only_mode"] = autor_only_mode

        # Set default widok to "tabela" if not provided
        context["widok"] = self.request.GET.get("widok", "tabela")

        # Zachowaj parametry filtru
        context["request"] = self.request

        # Update context with data from helper methods
        if not autor_only_mode:
            context.update(self._get_filtered_autor_context())
        context.update(self._get_jednostki_wydzialy_context())
        context.update(self._get_dyscypliny_context())
        context.update(self._get_statistics_context())
        context.update(self._get_status_context())

        # Calculate 3D metrics if needed
        self._calculate_3d_metrics(context.get("metryki", []), context["widok"])

        return context
