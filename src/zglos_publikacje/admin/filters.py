# Register your models here.
from django.contrib.admin import SimpleListFilter
from django.db.models import Window
from django.db.models.functions import ExtractWeekDay, FirstValue

from bpp.models import Wydzial
from zglos_publikacje.models import Zgloszenie_Publikacji_Autor


class WydzialJednostkiPierwszegoAutora(SimpleListFilter):
    title = "wydział 1-go autora"
    parameter_name = "wydz1a"
    db_field_name = "zgloszenie_publikacji_autor__jednostka__wydzial"

    def lookups(self, request, model_admin):
        return [
            (x.pk, x.nazwa)
            for x in Wydzial.objects.filter(
                pk__in=Zgloszenie_Publikacji_Autor.objects.filter(
                    jednostka__skupia_pracownikow=True
                )
                .values_list("jednostka__wydzial__pk")
                .distinct()
            )
        ]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if not v:
            return queryset

        jednostki_wybranego_wydzialu = list(
            Wydzial.objects.get(pk=v).aktualne_jednostki().values_list("pk", flat=True)
        )

        pierwsze_nieobce_jednostki = (
            Zgloszenie_Publikacji_Autor.objects.filter(
                jednostka__skupia_pracownikow=True
            )
            .annotate(
                pierwsza_nieobca_jednostka=Window(
                    expression=FirstValue("jednostka_id"),
                    partition_by=["rekord_id"],
                    order_by=("kolejnosc",),
                )
            )
            .values_list("rekord_id", "pierwsza_nieobca_jednostka")
            .distinct()
        )

        rekordy = [
            rekord_id
            for rekord_id, pierwsza_nieobca_jednostka_id in pierwsze_nieobce_jednostki
            if pierwsza_nieobca_jednostka_id in jednostki_wybranego_wydzialu
        ]

        return queryset.filter(pk__in=rekordy)


class DzienTygodniaFilter(SimpleListFilter):
    """Filtr dla dnia tygodnia utworzenia zgłoszenia"""

    title = "dzień tygodnia utworzenia"
    parameter_name = "weekday"

    def lookups(self, request, model_admin):
        return [
            ("2", "Poniedziałek"),
            ("3", "Wtorek"),
            ("4", "Środa"),
            ("5", "Czwartek"),
            ("6", "Piątek"),
            ("7", "Sobota"),
            ("1", "Niedziela"),
        ]

    def queryset(self, request, queryset):
        if self.value():
            # PostgreSQL: 1=Niedziela, 2=Poniedziałek, ..., 7=Sobota
            return queryset.annotate(weekday=ExtractWeekDay("utworzono")).filter(
                weekday=int(self.value())
            )
        return queryset


class MaPlikFilter(SimpleListFilter):
    """Filtr czy zgłoszenie ma załączony plik"""

    title = "ma załączony plik"
    parameter_name = "ma_plik"

    def lookups(self, request, model_admin):
        return [("brak", "brak pliku"), ("jest", "ma plik")]

    def queryset(self, request, queryset):
        v = self.value()

        if v == "brak":
            return queryset.filter(plik="")
        elif v == "jest":
            return queryset.exclude(plik="")

        return queryset


class MaPrzyczyneZwrotuFilter(SimpleListFilter):
    """Filtr czy zgłoszenie ma wypełnioną przyczynę zwrotu"""

    title = "ma przyczynę zwrotu"
    parameter_name = "ma_przyczyne_zwrotu"

    def lookups(self, request, model_admin):
        return [("brak", "brak przyczyny"), ("jest", "ma przyczynę")]

    def queryset(self, request, queryset):
        v = self.value()

        if v == "brak":
            return queryset.filter(przyczyna_zwrotu="") | queryset.filter(
                przyczyna_zwrotu=None
            )
        elif v == "jest":
            return queryset.exclude(przyczyna_zwrotu="").exclude(przyczyna_zwrotu=None)

        return queryset
