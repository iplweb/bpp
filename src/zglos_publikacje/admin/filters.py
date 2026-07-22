# Register your models here.
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, Window
from django.db.models.functions import ExtractWeekDay, FirstValue

from bpp.models import Jednostka
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor


class WydzialJednostkiPierwszegoAutora(SimpleListFilter):
    title = "wydział 1-go autora"
    parameter_name = "wydz1a"
    db_field_name = "zgloszenie_publikacji_autor__jednostka__wydzial"

    def lookups(self, request, model_admin):
        # Faza B (#438): „wydział" = jednostka-korzeń (self-FK). ``jednostka__
        # wydzial__pk`` to teraz pk korzenia — listujemy korzenie.
        return [
            (x.pk, x.nazwa)
            for x in Jednostka.objects.filter(
                parent__isnull=True,
                pk__in=Zgloszenie_Publikacji_Autor.objects.filter(
                    jednostka__skupia_pracownikow=True
                )
                .values_list("jednostka__wydzial__pk")
                .distinct(),
            )
        ]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if not v:
            return queryset

        # Faza B (#438): ``v`` to pk jednostki-korzenia; jednostki „w tym
        # wydziale" = poddrzewo korzenia (``wydzial_id == v``, self-FK) ORAZ
        # sam korzeń (``pk == v``; korzeń ma ``wydzial=NULL``, więc bez tego
        # gubimy zgłoszenia autora siedzącego bezpośrednio w jednostce-wydziale).
        jednostki_wybranego_wydzialu = list(
            Jednostka.objects.filter(Q(wydzial_id=v) | Q(pk=v)).values_list(
                "pk", flat=True
            )
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


class StanObslugiFilter(SimpleListFilter):
    """Filtr „Do obsługi / Załatwione / Wszystkie" (FD#443).

    Domyślnie (brak parametru w URL-u) lista pokazuje wyłącznie zgłoszenia
    wymagające reakcji operatora — bez odrzuconych, spamu i tych domkniętych
    importerem. „Wszystkie" trzeba wybrać jawnie.

    ``WYMAGA_ZMIAN`` świadomie nie należy do żadnej z dwóch grup: zgłoszenie
    jest wtedy w rękach autora (aktywny ``kod_do_edycji``), więc ani nie
    czeka na operatora, ani nie jest załatwione.
    """

    title = "stan obsługi"
    parameter_name = "stan_obslugi"

    DO_OBSLUGI = "do_obslugi"
    ZALATWIONE = "zalatwione"
    WSZYSTKIE = "wszystkie"

    STATUSY_DO_OBSLUGI = (
        Zgloszenie_Publikacji.Statusy.NOWY,
        Zgloszenie_Publikacji.Statusy.PO_ZMIANACH,
    )
    STATUSY_ZALATWIONE = (
        Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY,
        Zgloszenie_Publikacji.Statusy.ZAAKCEPTOWANY,
        Zgloszenie_Publikacji.Statusy.ODRZUCONO,
        Zgloszenie_Publikacji.Statusy.SPAM,
    )

    def lookups(self, request, model_admin):
        return [
            (self.DO_OBSLUGI, "Do obsługi"),
            (self.ZALATWIONE, "Załatwione"),
            (self.WSZYSTKIE, "Wszystkie"),
        ]

    def choices(self, changelist):
        # Nadpisujemy domyślne zachowanie ``SimpleListFilter``: tam brak
        # parametru = „Wszystkie" i dodatkowa pozycja z ``value=None``. U nas
        # brak parametru = „Do obsługi", a „Wszystkie" jest jawną wartością —
        # inaczej nie dałoby się jej wybrać z poziomu interfejsu.
        value = self.value()
        for lookup, title in self.lookup_choices:
            yield {
                "selected": value == lookup
                or (value is None and lookup == self.DO_OBSLUGI),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        value = self.value()

        if value == self.WSZYSTKIE:
            return queryset

        if value == self.ZALATWIONE:
            return queryset.filter(status__in=self.STATUSY_ZALATWIONE)

        # Domyślnie (brak parametru) oraz jawne „Do obsługi".
        return queryset.filter(status__in=self.STATUSY_DO_OBSLUGI)


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
