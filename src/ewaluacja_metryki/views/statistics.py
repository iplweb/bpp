from django.db.models import Avg, Count, Sum
from django.views.generic import ListView

from ..models import MetrykaAutora
from .mixins import EwaluacjaRequiredMixin


class StatystykiView(EwaluacjaRequiredMixin, ListView):
    model = MetrykaAutora
    template_name = "ewaluacja_metryki/statystyki.html"
    context_object_name = "top_autorzy_pkd"  # Renamed for clarity

    def get_queryset(self):
        # Top 20 autorów wg średniej PKDaut/slot
        return MetrykaAutora.objects.select_related(
            "autor", "dyscyplina_naukowa", "jednostka"
        ).order_by("-srednia_za_slot_nazbierana")[:20]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Keep the old name for backward compatibility in template
        context["top_autorzy"] = context["top_autorzy_pkd"]

        # Top 20 autorów wg slotów wypełnionych (the absolute top - highest slot filling AND highest PKDaut/slot)
        context["top_autorzy_sloty"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(slot_nazbierany__gt=0)  # Exclude those with zero slots
            .order_by("-slot_nazbierany", "-srednia_za_slot_nazbierana")[:20]
        )

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

        # Najniższe 20 autorów wg PKDaut/slot (nie-zerowych)
        context["bottom_autorzy_pkd"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(srednia_za_slot_nazbierana__gt=0)
            .order_by("srednia_za_slot_nazbierana")[:20]
        )

        # Najniższe 20 autorów wg slotów wypełnionych (nie-zerowych)
        context["bottom_autorzy_sloty"] = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(slot_nazbierany__gt=0)
            .order_by("slot_nazbierany")[:20]
        )

        # Autorzy zerowi z latami
        from bpp.models import Autor_Dyscyplina

        autorzy_zerowi_raw = (
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            )
            .filter(srednia_za_slot_nazbierana=0)
            .order_by("autor__nazwisko", "autor__imiona")
        )

        # Dodaj informację o latach dla każdego autora zerowego
        # TYLKO dla lat gdzie rodzaj_autora.jest_w_n = True
        autorzy_zerowi = []
        for metryka in autorzy_zerowi_raw:
            # Pobierz lata, w których autor był przypisany do dyscypliny
            # TYLKO dla rodzajów autorów z jest_w_n = True
            lata_dyscypliny = (
                Autor_Dyscyplina.objects.filter(
                    autor=metryka.autor,
                    dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                    rok__gte=metryka.rok_min,
                    rok__lte=metryka.rok_max,
                    rodzaj_autora__jest_w_n=True,
                )
                .values_list("rok", flat=True)
                .order_by("rok")
            )

            lata_list = list(lata_dyscypliny)
            # Dodaj do listy tylko jeśli autor ma przynajmniej jeden rok z jest_w_n=True
            if lata_list:
                metryka.lata_zerowe = lata_list
                autorzy_zerowi.append(metryka)

        context["autorzy_zerowi"] = autorzy_zerowi

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
