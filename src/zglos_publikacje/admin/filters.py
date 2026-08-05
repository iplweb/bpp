# Register your models here.
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, Window
from django.db.models.functions import ExtractWeekDay, FirstValue
from djangoql.admin import DJANGOQL_SEARCH_MARKER

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
    będące w toku — bez zaakceptowanych, odrzuconych, spamu i tych
    domkniętych importerem. „Wszystkie" trzeba wybrać jawnie.

    ``WYMAGA_ZMIAN`` należy do „Do obsługi": zgłoszenie siedzi wprawdzie u
    autora (aktywny ``kod_do_edycji``), ale wciąż jest na biurku operatora —
    trzeba je pilnować, przypomnieć, po czasie odrzucić. Do „Załatwionych"
    nie należy na pewno, a wyrzucenie go poza obie grupy chowało zgłoszenia
    czekające na autora wszędzie poza „Wszystkie" — regres widoczności
    danych wobec stanu sprzed FD#443.

    Filtr jest **przezroczysty**, gdy stan obsługi nie został wybrany
    ręcznie, a w URL-u siedzi jawny wybór z sąsiedniego filtra „status"
    (``status__exact`` itp.). Bez tego oba filtry składałyby się koniunkcją
    i kliknięcie „status → spam" dawało pustą listę bez wyjaśnienia.
    """

    title = "stan obsługi"
    parameter_name = "stan_obslugi"

    #: Pola sąsiednich filtrów z ``list_filter``, których jawny wybór ma
    #: wyłączyć domyślne zawężenie. Parametry w URL-u to ``<pole>`` albo
    #: ``<pole>__<lookup>``.
    #:
    #: ``status`` — bo inaczej „status → spam" wpadałby w koniunkcję
    #: z ``status__in=(0, 2, 3)`` i dawał pustą listę.
    #:
    #: ``zaimportowal``/``zaimportowano`` — bo te pola są niepuste
    #: **wyłącznie** na zgłoszeniach ZAIMPORTOWANYCH, czyli spoza grupy
    #: „Do obsługi". Bez nich koniunkcja jest sprzeczna z definicji
    #: i kliknięcie osoby w filtrze „zaimportował" ZAWSZE dawało zero
    #: wyników — dokładnie ta klasa błędu, którą naprawia ``status``.
    POLA_WYLACZAJACE_ZAWEZENIE = ("status", "zaimportowal", "zaimportowano")

    DO_OBSLUGI = "do_obslugi"
    ZALATWIONE = "zalatwione"
    WSZYSTKIE = "wszystkie"

    STATUSY_DO_OBSLUGI = (
        Zgloszenie_Publikacji.Statusy.NOWY,
        Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN,
        Zgloszenie_Publikacji.Statusy.PO_ZMIANACH,
    )
    STATUSY_ZALATWIONE = (
        Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY,
        Zgloszenie_Publikacji.Statusy.ZAAKCEPTOWANY,
        Zgloszenie_Publikacji.Statusy.ODRZUCONO,
        Zgloszenie_Publikacji.Statusy.SPAM,
    )

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        # ``request.GET``, nie ``params``: Django zdejmuje z ``params`` klucze
        # skonsumowane przez kolejne filtry, a nas interesuje surowy URL.
        self.status_wybrany_recznie = self._inny_filtr_wybrany(
            request
        ) or self._djangoql_aktywne(request)

    @classmethod
    def _inny_filtr_wybrany(cls, request) -> bool:
        """Czy operator wybrał ręcznie któryś z sąsiednich filtrów?"""
        return any(
            klucz == pole or klucz.startswith(f"{pole}__")
            for klucz in request.GET
            for pole in cls.POLA_WYLACZAJACE_ZAWEZENIE
        )

    @staticmethod
    def _djangoql_aktywne(request) -> bool:
        """Czy operator pisze własne zapytanie DjangoQL?

        Ten admin ma ``DjangoQLSearchMixin``, a zapytanie ląduje w ``q``
        (marker trybu to ``q-l=on``) — czyli poza polem ``status``, którego
        pilnuje detekcja wyżej. Bez tego ``status = 5`` wpisane w DjangoQL
        wpadałoby w koniunkcję z domyślnym ``status__in=(0, 2, 3)`` i zawsze
        zwracało pustą listę: operator szukający spamu dostawał zero wyników.

        Skoro operator pisze zapytanie ręcznie, domyślne zawężenie ma zejść
        mu z drogi — tak samo jak przy jawnym wyborze w filtrze „status".

        Sam przełączony tryb bez treści zapytania (``q`` puste) nie liczy się
        jako wybór: operator jeszcze nic nie napisał, więc domyślny widok
        „Do obsługi" ma zostać.
        """
        return request.GET.get(DJANGOQL_SEARCH_MARKER) == "on" and bool(
            request.GET.get("q", "").strip()
        )

    def lookups(self, request, model_admin):
        return [
            (self.DO_OBSLUGI, "Do obsługi"),
            (self.ZALATWIONE, "Załatwione"),
            (self.WSZYSTKIE, "Wszystkie"),
        ]

    def czy_domyslne_zawezenie(self) -> bool:
        """Czy filtr działa „z automatu" (brak wyboru użytkownika)?"""
        return self.value() is None and not self.status_wybrany_recznie

    def choices(self, changelist):
        # Nadpisujemy domyślne zachowanie ``SimpleListFilter``: tam brak
        # parametru = „Wszystkie" i dodatkowa pozycja z ``value=None``. U nas
        # brak parametru = „Do obsługi", a „Wszystkie" jest jawną wartością —
        # inaczej nie dałoby się jej wybrać z poziomu interfejsu.
        #
        # Gdy filtr jest przezroczysty (wybór w filtrze „status"), nie
        # zaznaczamy nic — inaczej podświetlone „Do obsługi" kłamałoby o tym,
        # co realnie zawęża listę.
        value = self.value()
        domyslne = self.czy_domyslne_zawezenie()
        for lookup, title in self.lookup_choices:
            yield {
                "selected": value == lookup or (domyslne and lookup == self.DO_OBSLUGI),
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

        if value is None and self.status_wybrany_recznie:
            # Jawny wybór w filtrze „status" wygrywa z domyślnym zawężeniem —
            # inaczej „status → spam" dawałoby pustą listę bez wyjaśnienia.
            return queryset

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
