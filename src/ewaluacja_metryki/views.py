from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import DetailView, ListView

from .models import MetrykaAutora, StatusGenerowania
from .tasks import generuj_metryki_task

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.utils.decorators import method_decorator

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Jednostka, Wydzial
from bpp.models.uczelnia import Uczelnia


def ma_uprawnienia_ewaluacji(user):
    """Sprawdza czy użytkownik ma uprawnienia do ewaluacji"""
    return user.is_superuser or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


class EwaluacjaRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin wymagający uprawnień do ewaluacji"""

    def test_func(self):
        return ma_uprawnienia_ewaluacji(self.request.user)


class MetrykiListView(EwaluacjaRequiredMixin, ListView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/lista.html"
    context_object_name = "metryki"
    paginate_by = 50

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

        # Sortowanie
        sort = self.request.GET.get("sort", "-srednia_za_slot_nazbierana")
        if sort in [
            "srednia_za_slot_nazbierana",
            "-srednia_za_slot_nazbierana",
            "procent_wykorzystania_slotow",
            "-procent_wykorzystania_slotow",
            "autor__nazwisko",
            "-autor__nazwisko",
        ]:
            queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Jeśli filtrujemy po ID autora, pobierz dane autora
        autor_id = self.request.GET.get("autor_id")
        if autor_id:
            from bpp.models import Autor

            try:
                autor = Autor.objects.get(pk=autor_id)
                context["filtered_autor"] = autor
            except Autor.DoesNotExist:
                pass

        # Sprawdź czy uczelnia używa wydziałów
        uczelnia = Uczelnia.objects.get_default()
        context["uzywa_wydzialow"] = uczelnia.uzywaj_wydzialow if uczelnia else False

        # Listy do filtrów
        context["jednostki"] = (
            Jednostka.objects.filter(metryka_autora__isnull=False)
            .distinct()
            .order_by("nazwa")
        )

        if context["uzywa_wydzialow"]:
            context["wydzialy"] = (
                Wydzial.objects.filter(jednostka__metryka_autora__isnull=False)
                .distinct()
                .order_by("nazwa")
            )

        from bpp.models import Dyscyplina_Naukowa

        context["dyscypliny"] = (
            Dyscyplina_Naukowa.objects.filter(metrykaautora__isnull=False)
            .distinct()
            .order_by("nazwa")
        )

        # Statystyki
        stats = self.get_queryset().aggregate(
            srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
            srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
            liczba_wierszy=Count("id"),
            liczba_autorow=Count("autor", distinct=True),
        )
        context["statystyki"] = stats

        # Zachowaj parametry filtru
        context["request"] = self.request

        # Dodaj informację o ostatnim generowaniu
        context["status_generowania"] = StatusGenerowania.get_or_create()

        return context


class MetrykaDetailView(EwaluacjaRequiredMixin, DetailView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/szczegoly.html"
    context_object_name = "metryka"

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

        # Pobierz dane Autor_Dyscyplina dla lat 2022-2025
        from bpp.models import Autor_Dyscyplina

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

        # Pobierz szczegóły prac nazbieranych
        if metryka.prace_nazbierane:
            from bpp.models.cache import Cache_Punktacja_Autora_Query

            prace_nazbierane = (
                Cache_Punktacja_Autora_Query.objects.filter(
                    pk__in=metryka.prace_nazbierane
                )
                .select_related("rekord")
                .order_by("-pkdaut")
            )

            # Calculate pkdaut/slot for each work
            for praca in prace_nazbierane:
                if praca.slot and praca.slot > 0:
                    praca.pkdaut_per_slot = float(praca.pkdaut) / float(praca.slot)
                else:
                    praca.pkdaut_per_slot = None

            context["prace_nazbierane"] = prace_nazbierane

        # Pobierz szczegóły wszystkich prac
        if metryka.prace_wszystkie:
            from bpp.models.cache import Cache_Punktacja_Autora_Query

            prace_wszystkie = (
                Cache_Punktacja_Autora_Query.objects.filter(
                    pk__in=metryka.prace_wszystkie
                )
                .select_related("rekord")
                .order_by("-pkdaut")
            )

            # Calculate pkdaut/slot for each work
            for praca in prace_wszystkie:
                if praca.slot and praca.slot > 0:
                    praca.pkdaut_per_slot = float(praca.pkdaut) / float(praca.slot)
                else:
                    praca.pkdaut_per_slot = None

            context["prace_wszystkie"] = prace_wszystkie

        # Porównanie z innymi autorami w jednostce
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


class StatystykiView(EwaluacjaRequiredMixin, ListView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/statystyki.html"
    context_object_name = "top_autorzy"

    def get_queryset(self):
        # Top 20 autorów wg średniej za slot
        return MetrykaAutora.objects.select_related(
            "autor", "dyscyplina_naukowa", "jednostka"
        ).order_by("-srednia_za_slot_nazbierana")[:20]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statystyki globalne
        wszystkie = MetrykaAutora.objects.all()
        context["statystyki_globalne"] = wszystkie.aggregate(
            liczba_wierszy=Count("id"),
            liczba_autorow=Count("autor", distinct=True),
            srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
            srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
            suma_punktow=Sum("punkty_nazbierane"),
            suma_slotow=Sum("slot_nazbierany"),
        )

        # Bottom 20 autorów wg PKDaut/slot (nie-zerowych)
        context["bottom_autorzy_pkd"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(srednia_za_slot_nazbierana__gt=0)
            .order_by("srednia_za_slot_nazbierana")[:20]
        )

        # Bottom 20 autorów wg slotów wypełnionych (nie-zerowych)
        context["bottom_autorzy_sloty"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(slot_nazbierany__gt=0)
            .order_by("slot_nazbierany")[:20]
        )

        # Autorzy zerowi
        context["autorzy_zerowi"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(srednia_za_slot_nazbierana=0)
            .order_by("autor__nazwisko", "autor__imiona")
        )

        # Statystyki wg jednostek
        jednostki_stats = (
            MetrykaAutora.objects.values("jednostka__nazwa", "jednostka__skrot")
            .annotate(
                liczba_autorow=Count("id"),
                srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
                srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
                suma_punktow=Sum("punkty_nazbierane"),
            )
            .order_by("-srednia_pkd_slot")[:10]
        )
        context["jednostki_stats"] = jednostki_stats

        # Statystyki wg dyscyplin
        dyscypliny_stats = (
            MetrykaAutora.objects.values(
                "dyscyplina_naukowa__nazwa", "dyscyplina_naukowa__kod"
            )
            .annotate(
                liczba_autorow=Count("id"),
                srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
                srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
                suma_punktow=Sum("punkty_nazbierane"),
            )
            .order_by("-srednia_pkd_slot")
        )
        context["dyscypliny_stats"] = dyscypliny_stats

        # Rozkład wykorzystania slotów
        context["wykorzystanie_ranges"] = {
            "0-25%": wszystkie.filter(procent_wykorzystania_slotow__lt=25).count(),
            "25-50%": wszystkie.filter(
                procent_wykorzystania_slotow__gte=25,
                procent_wykorzystania_slotow__lt=50,
            ).count(),
            "50-75%": wszystkie.filter(
                procent_wykorzystania_slotow__gte=50,
                procent_wykorzystania_slotow__lt=75,
            ).count(),
            "75-99%": wszystkie.filter(
                procent_wykorzystania_slotow__gte=75,
                procent_wykorzystania_slotow__lt=99,
            ).count(),
            "99-100%": wszystkie.filter(procent_wykorzystania_slotow__gte=99).count(),
        }

        return context


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class UruchomGenerowanieView(View):
    """Widok do uruchamiania generowania metryk przez Celery task"""

    def post(self, request, *args, **kwargs):
        # Dodatkowe sprawdzenie uprawnień do generowania (tylko staff)
        if not request.user.is_staff:
            messages.error(request, "Nie masz uprawnień do uruchomienia generowania.")
            return redirect("ewaluacja_metryki:lista")

        # Sprawdź czy generowanie nie jest już w trakcie
        status = StatusGenerowania.get_or_create()
        if status.w_trakcie:
            messages.warning(
                request,
                f"Generowanie jest już w trakcie (rozpoczęte: {status.data_rozpoczecia.strftime('%Y-%m-%d %H:%M:%S')})",
            )
            return redirect("ewaluacja_metryki:lista")

        # Pobierz parametry z formularza (jeśli są)
        rok_min = int(request.POST.get("rok_min", 2022))
        rok_max = int(request.POST.get("rok_max", 2025))
        minimalny_pk = float(request.POST.get("minimalny_pk", 0.01))
        nadpisz = request.POST.get("nadpisz", "on") == "on"

        # Uruchom task (z domyślnym przeliczaniem liczby N)
        result = generuj_metryki_task.delay(
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=minimalny_pk,
            nadpisz=nadpisz,
            przelicz_liczbe_n=True,  # Zawsze przeliczaj liczbę N przy generowaniu metryk
        )

        messages.success(
            request,
            f"Generowanie metryk zostało uruchomione (ID zadania: {result.id}). "
            "Odśwież stronę za chwilę, aby zobaczyć postęp.",
        )

        return redirect("ewaluacja_metryki:lista")

    def get(self, request, *args, **kwargs):
        # GET przekierowuje do listy
        return redirect("ewaluacja_metryki:lista")


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class StatusGenerowaniaView(View):
    """Widok zwracający status generowania jako JSON (dla AJAX)"""

    def get(self, request, *args, **kwargs):
        status = StatusGenerowania.get_or_create()

        return JsonResponse(
            {
                "w_trakcie": status.w_trakcie,
                "data_rozpoczecia": (
                    status.data_rozpoczecia.isoformat()
                    if status.data_rozpoczecia
                    else None
                ),
                "data_zakonczenia": (
                    status.data_zakonczenia.isoformat()
                    if status.data_zakonczenia
                    else None
                ),
                "liczba_przetworzonych": status.liczba_przetworzonych,
                "liczba_bledow": status.liczba_bledow,
                "ostatni_komunikat": status.ostatni_komunikat,
                "procent": (
                    (status.liczba_przetworzonych / 100 * 100)
                    if status.w_trakcie and status.liczba_przetworzonych > 0
                    else 0
                ),
            }
        )


@method_decorator(user_passes_test(ma_uprawnienia_ewaluacji), name="dispatch")
class ExportStatystykiXLSX(View):
    """Export statistics tables to XLSX format"""

    def get(self, request, table_type):
        import datetime

        from django.http import HttpResponse
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        # Create workbook
        wb = Workbook()
        ws = wb.active

        # Define header style
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="366092", end_color="366092", fill_type="solid"
        )
        header_alignment = Alignment(horizontal="center", vertical="center")

        if table_type == "globalne":
            ws.title = "Statystyki globalne"
            # Get statistics
            wszystkie = MetrykaAutora.objects.all()
            stats = wszystkie.aggregate(
                liczba_wierszy=Count("id"),
                liczba_autorow=Count("autor", distinct=True),
                srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
                srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
                suma_punktow=Sum("punkty_nazbierane"),
                suma_slotow=Sum("slot_nazbierany"),
            )

            # Headers
            headers = ["Metryka", "Wartość"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            # Data
            data = [
                ("Liczba wierszy", stats["liczba_wierszy"] or 0),
                ("Liczba autorów", stats["liczba_autorow"] or 0),
                (
                    "Średnie wykorzystanie slotów (%)",
                    f"{stats['srednia_wykorzystania'] or 0:.1f}",
                ),
                ("Średnia PKDaut/slot", f"{stats['srednia_pkd_slot'] or 0:.2f}"),
                ("Suma punktów", f"{stats['suma_punktow'] or 0:.0f}"),
                ("Suma slotów", f"{stats['suma_slotow'] or 0:.0f}"),
            ]

            for row_idx, (label, value) in enumerate(data, 2):
                ws.cell(row=row_idx, column=1, value=label)
                ws.cell(row=row_idx, column=2, value=value)

        elif table_type == "top-autorzy":
            ws.title = "Top 20 autorów"
            queryset = MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            ).order_by("-srednia_za_slot_nazbierana")[:20]

            headers = [
                "Lp.",
                "Autor",
                "Jednostka",
                "Dyscyplina",
                "Sloty wypełnione",
                "% wykorzystania",
                "PKDaut/slot",
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, metryka in enumerate(queryset, 2):
                ws.cell(row=row_idx, column=1, value=row_idx - 1)
                ws.cell(row=row_idx, column=2, value=str(metryka.autor))
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=metryka.jednostka.nazwa if metryka.jednostka else "-",
                )
                ws.cell(
                    row=row_idx,
                    column=4,
                    value=(
                        metryka.dyscyplina_naukowa.nazwa
                        if metryka.dyscyplina_naukowa
                        else "-"
                    ),
                )
                ws.cell(row=row_idx, column=5, value=float(metryka.slot_nazbierany))
                ws.cell(
                    row=row_idx,
                    column=6,
                    value=float(metryka.procent_wykorzystania_slotow),
                )
                ws.cell(
                    row=row_idx,
                    column=7,
                    value=float(metryka.srednia_za_slot_nazbierana),
                )

        elif table_type == "bottom-pkd":
            ws.title = "Bottom 20 PKDaut-slot"
            queryset = (
                MetrykaAutora.objects.select_related(
                    "autor", "dyscyplina_naukowa", "jednostka"
                )
                .filter(srednia_za_slot_nazbierana__gt=0)
                .order_by("srednia_za_slot_nazbierana")[:20]
            )

            headers = [
                "Lp.",
                "Autor",
                "Jednostka",
                "Dyscyplina",
                "Sloty wypełnione",
                "% wykorzystania",
                "PKDaut/slot",
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, metryka in enumerate(queryset, 2):
                ws.cell(row=row_idx, column=1, value=row_idx - 1)
                ws.cell(row=row_idx, column=2, value=str(metryka.autor))
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=metryka.jednostka.nazwa if metryka.jednostka else "-",
                )
                ws.cell(
                    row=row_idx,
                    column=4,
                    value=(
                        metryka.dyscyplina_naukowa.nazwa
                        if metryka.dyscyplina_naukowa
                        else "-"
                    ),
                )
                ws.cell(row=row_idx, column=5, value=float(metryka.slot_nazbierany))
                ws.cell(
                    row=row_idx,
                    column=6,
                    value=float(metryka.procent_wykorzystania_slotow),
                )
                ws.cell(
                    row=row_idx,
                    column=7,
                    value=float(metryka.srednia_za_slot_nazbierana),
                )

        elif table_type == "bottom-sloty":
            ws.title = "Bottom 20 sloty wypełnione"
            queryset = (
                MetrykaAutora.objects.select_related(
                    "autor", "dyscyplina_naukowa", "jednostka"
                )
                .filter(slot_nazbierany__gt=0)
                .order_by("slot_nazbierany")[:20]
            )

            headers = [
                "Lp.",
                "Autor",
                "Jednostka",
                "Dyscyplina",
                "Sloty wypełnione",
                "% wykorzystania",
                "PKDaut/slot",
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, metryka in enumerate(queryset, 2):
                ws.cell(row=row_idx, column=1, value=row_idx - 1)
                ws.cell(row=row_idx, column=2, value=str(metryka.autor))
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=metryka.jednostka.nazwa if metryka.jednostka else "-",
                )
                ws.cell(
                    row=row_idx,
                    column=4,
                    value=(
                        metryka.dyscyplina_naukowa.nazwa
                        if metryka.dyscyplina_naukowa
                        else "-"
                    ),
                )
                ws.cell(row=row_idx, column=5, value=float(metryka.slot_nazbierany))
                ws.cell(
                    row=row_idx,
                    column=6,
                    value=float(metryka.procent_wykorzystania_slotow),
                )
                ws.cell(
                    row=row_idx,
                    column=7,
                    value=float(metryka.srednia_za_slot_nazbierana),
                )

        elif table_type == "zerowi":
            ws.title = "Autorzy zerowi"
            queryset = (
                MetrykaAutora.objects.select_related(
                    "autor", "dyscyplina_naukowa", "jednostka"
                )
                .filter(srednia_za_slot_nazbierana=0)
                .order_by("autor__nazwisko", "autor__imiona")
            )

            headers = ["Lp.", "Autor", "Jednostka", "Dyscyplina", "Lata"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, metryka in enumerate(queryset, 2):
                ws.cell(row=row_idx, column=1, value=row_idx - 1)
                ws.cell(row=row_idx, column=2, value=str(metryka.autor))
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=metryka.jednostka.nazwa if metryka.jednostka else "-",
                )
                ws.cell(
                    row=row_idx,
                    column=4,
                    value=(
                        metryka.dyscyplina_naukowa.nazwa
                        if metryka.dyscyplina_naukowa
                        else "-"
                    ),
                )
                ws.cell(
                    row=row_idx, column=5, value=f"{metryka.rok_min}-{metryka.rok_max}"
                )

        elif table_type == "jednostki":
            ws.title = "Statystyki jednostek"
            stats = (
                MetrykaAutora.objects.values("jednostka__nazwa", "jednostka__skrot")
                .annotate(
                    liczba_autorow=Count("id"),
                    srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
                    srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
                    suma_punktow=Sum("punkty_nazbierane"),
                )
                .order_by("-srednia_pkd_slot")[:10]
            )

            headers = [
                "Jednostka",
                "Liczba autorów",
                "Śr. wykorzystanie (%)",
                "Śr. PKDaut/slot",
                "Suma punktów",
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, stat in enumerate(stats, 2):
                nazwa = stat["jednostka__nazwa"] or "-"
                if stat["jednostka__skrot"]:
                    nazwa = f"{nazwa} ({stat['jednostka__skrot']})"
                ws.cell(row=row_idx, column=1, value=nazwa)
                ws.cell(row=row_idx, column=2, value=stat["liczba_autorow"])
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=f"{stat['srednia_wykorzystania'] or 0:.1f}",
                )
                ws.cell(
                    row=row_idx, column=4, value=f"{stat['srednia_pkd_slot'] or 0:.2f}"
                )
                ws.cell(row=row_idx, column=5, value=f"{stat['suma_punktow'] or 0:.0f}")

        elif table_type == "dyscypliny":
            ws.title = "Statystyki dyscyplin"
            stats = (
                MetrykaAutora.objects.values(
                    "dyscyplina_naukowa__nazwa", "dyscyplina_naukowa__kod"
                )
                .annotate(
                    liczba_autorow=Count("id"),
                    srednia_wykorzystania=Avg("procent_wykorzystania_slotow"),
                    srednia_pkd_slot=Avg("srednia_za_slot_nazbierana"),
                    suma_punktow=Sum("punkty_nazbierane"),
                )
                .order_by("-srednia_pkd_slot")
            )

            headers = [
                "Dyscyplina",
                "Kod",
                "Liczba autorów",
                "Śr. wykorzystanie (%)",
                "Śr. PKDaut/slot",
                "Suma punktów",
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            for row_idx, stat in enumerate(stats, 2):
                ws.cell(
                    row=row_idx,
                    column=1,
                    value=stat["dyscyplina_naukowa__nazwa"] or "-",
                )
                ws.cell(
                    row=row_idx, column=2, value=stat["dyscyplina_naukowa__kod"] or "-"
                )
                ws.cell(row=row_idx, column=3, value=stat["liczba_autorow"])
                ws.cell(
                    row=row_idx,
                    column=4,
                    value=f"{stat['srednia_wykorzystania'] or 0:.1f}",
                )
                ws.cell(
                    row=row_idx, column=5, value=f"{stat['srednia_pkd_slot'] or 0:.2f}"
                )
                ws.cell(row=row_idx, column=6, value=f"{stat['suma_punktow'] or 0:.0f}")

        elif table_type == "wykorzystanie":
            ws.title = "Rozkład wykorzystania slotów"
            wszystkie = MetrykaAutora.objects.all()

            headers = ["Przedział", "Liczba wierszy", "Procent"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            total = wszystkie.count()
            ranges = [
                (
                    "0-25%",
                    wszystkie.filter(procent_wykorzystania_slotow__lt=25).count(),
                ),
                (
                    "25-50%",
                    wszystkie.filter(
                        procent_wykorzystania_slotow__gte=25,
                        procent_wykorzystania_slotow__lt=50,
                    ).count(),
                ),
                (
                    "50-75%",
                    wszystkie.filter(
                        procent_wykorzystania_slotow__gte=50,
                        procent_wykorzystania_slotow__lt=75,
                    ).count(),
                ),
                (
                    "75-99%",
                    wszystkie.filter(
                        procent_wykorzystania_slotow__gte=75,
                        procent_wykorzystania_slotow__lt=99,
                    ).count(),
                ),
                (
                    "99-100%",
                    wszystkie.filter(procent_wykorzystania_slotow__gte=99).count(),
                ),
            ]

            for row_idx, (range_name, count) in enumerate(ranges, 2):
                ws.cell(row=row_idx, column=1, value=range_name)
                ws.cell(row=row_idx, column=2, value=count)
                ws.cell(
                    row=row_idx,
                    column=3,
                    value=f"{(count/total*100) if total > 0 else 0:.1f}%",
                )

        else:
            return HttpResponse("Nieznany typ tabeli", status=400)

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except BaseException:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Prepare response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"metryki_statystyki_{table_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        wb.save(response)
        return response
