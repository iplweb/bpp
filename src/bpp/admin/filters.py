from dal import autocomplete
from django import forms
from django.contrib.admin.filters import SimpleListFilter
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, F, IntegerField, Max, Q
from django.db.models.functions import Cast

from bpp.models import BppUser, Uczelnia, Wydawnictwo_Zwarte
from bpp.models.struktura import Jednostka


class SimpleIntegerFilter(SimpleListFilter):
    db_field_name = None

    def lookups(self, request, model_admin):
        return [
            ("brak", "wartość nie ustalona"),
            ("zero", "zero"),
            ("powyzej", "więcej, niż zero"),
        ]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            return queryset.filter(**{field: None})
        elif v == "zero":
            return queryset.filter(**{field: 0})
        elif v == "powyzej":
            return queryset.filter(**{field + "__gt": 0})

        return queryset


class SimpleNotNullFilter(SimpleListFilter):
    db_field_name = None

    def lookups(self, request, model_admin):
        return [("brak", "wartość nie ustalona"), ("jest", "wartość ustalona")]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            return queryset.filter(**{field: None})
        elif v == "jest":
            return queryset.exclude(**{field: None})

        return queryset


class BezJakichkolwiekDyscyplinFilter(SimpleListFilter):
    title = "Bez jakichkolwiek dyscyplin"
    parameter_name = "_bjkd_"
    db_field_name = None

    def lookups(self, request, model_admin):
        return [
            ("tak", "tak, brak dyscyplin"),
        ]

    def queryset(self, request, queryset):
        v = self.value()

        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "tak":
            return queryset.annotate(
                total_authors=Count("autorzy_set"),
                authors_without_discipline=Count(
                    "autorzy_set",
                    filter=Q(autorzy_set__dyscyplina_naukowa__isnull=True),
                ),
            ).filter(
                total_authors__gt=0,  # Ma autorów
                total_authors=F(
                    "authors_without_discipline"
                ),  # Wszyscy autorzy bez dyscypliny
            )

        return queryset


class JestWydawnictwemNadrzednymDlaFilter(SimpleNotNullFilter):
    title = "jest wydawnictwem nadrzędnym dla innego"
    parameter_name = "wyd_nad"

    def lookups(self, request, model_admin):
        return [("brak", "nie jest"), ("jest", "jest")]

    def queryset(self, request, queryset):
        v = self.value()
        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            return queryset.exclude(
                pk__in=Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych()
            )
        elif v == "jest":
            return queryset.filter(
                pk__in=Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych()
            )

        return queryset


class MaWydawnictwoNadrzedneFilter(SimpleNotNullFilter):
    title = "ma wydawnictwo nadrzędne"
    parameter_name = "ma_wyd_nad"

    def lookups(self, request, model_admin):
        return [("brak", "ma"), ("jest", "nie ma")]

    def queryset(self, request, queryset):
        v = self.value()
        field = self.db_field_name
        if field is None:
            field = self.parameter_name

        if v == "brak":
            # ma nadrzedne
            return queryset.exclude(wydawnictwo_nadrzedne_id=None)
        elif v == "jest":
            # nie ma nadrzednego
            return queryset.filter(wydawnictwo_nadrzedne_id=None)

        return queryset


class LiczbaZnakowFilter(SimpleIntegerFilter):
    title = "liczba znaków wydawniczych"
    parameter_name = "liczba_znakow_wydawniczych"


class DOIUstawioneFilter(SimpleNotNullFilter):
    title = "DOI ustawione"
    parameter_name = "doi"


class PBNIDObecnyFilter(SimpleNotNullFilter):
    title = "PBN ID"
    parameter_name = "pbn_id"


class OrcidObecnyFilter(SimpleNotNullFilter):
    title = "ORCID"
    parameter_name = "orcid"


class OrcidAutoraDyscyplinyObecnyFilter(SimpleNotNullFilter):
    title = "ORCID autora"
    parameter_name = "autor__orcid"


class PBN_UID_IDAutoraObecnyFilter(SimpleNotNullFilter):
    title = "PBN UID autora"
    parameter_name = "autor__pbn_uid_id"


class PBN_UID_IDObecnyFilter(SimpleNotNullFilter):
    title = "PBN UID"
    parameter_name = "pbn_uid_id"


class MniswIdObecnyFilter(SimpleNotNullFilter):
    # Uwaga: to NIE jest to samo, co PBN_UID_IDObecnyFilter. Źródło może mieć
    # pbn_uid (powiązany Journal), ale ten Journal może mieć mniswId = NULL.
    title = "mniswID"
    parameter_name = "mnisw_id"
    db_field_name = "pbn_uid__mniswId"

    def lookups(self, request, model_admin):
        return [("brak", "nie ma mniswID"), ("jest", "ma mniswID")]


class MaPublikacjeFilter(SimpleListFilter):
    # Filtruje po liczbie powiązanych Wydawnictw Ciągłych. Filtrowanie po
    # annotacji Count (a nie po wydawnictwo_ciagle__isnull) unika duplikatów
    # wierszy z JOIN-a — Count + GROUP BY zwija je do jednego wiersza na
    # źródło. ZrodloAdmin.get_queryset zwykle dostarcza już _liczba_prac;
    # dla bezpieczeństwa (moduł filtrów jest współdzielony) annotujemy ją tu
    # sami, gdy jej brak — inaczej filtr rzucałby FieldError.
    title = "ma publikacje"
    parameter_name = "ma_publikacje"

    def lookups(self, request, model_admin):
        return [("tak", "ma publikacje"), ("nie", "nie ma publikacji")]

    def queryset(self, request, queryset):
        v = self.value()
        if v not in ("tak", "nie"):
            return queryset
        if "_liczba_prac" not in queryset.query.annotations:
            queryset = queryset.annotate(
                _liczba_prac=Count("wydawnictwo_ciagle", distinct=True)
            )
        if v == "tak":
            return queryset.filter(_liczba_prac__gt=0)
        return queryset.filter(_liczba_prac=0)


class CalkowitaLiczbaAutorowFilter(SimpleIntegerFilter):
    title = "całkowita liczba autorów"
    parameter_name = "calkowita_liczba_autorow"


class WydzialFilter(SimpleListFilter):
    """Filtr changelisty JednostkaAdmin po „wydziale" (Faza B, #438).

    Zastępuje goły ``list_filter = ("wydzial", ...)``, który generował
    dropdown ze WSZYSTKIMI jednostkami (denorm ``wydzial`` jest self-FK do
    dowolnego węzła-korzenia). Tu:

    * opcje to WYŁĄCZNIE jednostki-korzenie (``parent IS NULL``) -- czyli
      dawne „wydziały" po konsolidacji (w multi-hosted zawężone do uczelni z
      requestu, spójnie z ``SiteFilteredAdminMixin``; superuser widzi wszystkie);
    * wybór filtruje CAŁE PODDRZEWO korzenia
      (``Q(wydzial_id=v) | Q(pk=v)`` -- potomkowie niosą ``wydzial=korzeń``,
      a ``| Q(pk=v)`` dokłada sam korzeń, wzorzec unii z reszty Fazy B);
    * filtr jest UKRYTY, gdy uczelnia nie używa wydziałów
      (``uzywaj_wydzialow=False``).
    """

    title = "Wydział"
    parameter_name = "wydzial"

    def __init__(self, request, params, model, model_admin):
        # SimpleListFilter.__init__ nie zapisuje ``request`` -- potrzebujemy go
        # w ``has_output`` (bramka ``uzywaj_wydzialow``), więc trzymamy go sami.
        self.request = request
        super().__init__(request, params, model, model_admin)

    def _uczelnia(self):
        return Uczelnia.objects.get_for_request(self.request)

    def has_output(self):
        # Ukryj filtr, gdy instytucja jest 1-progowa (nie używa wydziałów).
        # ``get_for_request`` degraduje do jedynej-albo-None (nie rzuca) --
        # gdy nie da się ustalić uczelni, nie ukrywamy (zachowanie domyślne).
        uczelnia = self._uczelnia()
        if uczelnia is not None and not uczelnia.uzywaj_wydzialow:
            return False
        return super().has_output()

    def lookups(self, request, model_admin):
        qs = Jednostka.objects.filter(parent__isnull=True, widoczna=True)
        # Multi-hosted: zwykły admin widzi tylko korzenie swojej uczelni
        # (parytet z SiteFilteredAdminMixin.get_queryset); superuser -- wszystkie.
        if not request.user.is_superuser:
            uczelnia = getattr(request, "_uczelnia", None)
            if uczelnia is not None:
                qs = qs.filter(uczelnia=uczelnia)
        return [
            (j.pk, str(j))
            for j in qs.order_by(*Jednostka.objects.get_default_ordering())
        ]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            return queryset.filter(Q(wydzial_id=v) | Q(pk=v))
        return queryset


class JednostkaFilter(SimpleListFilter):
    title = "Jednostka"
    parameter_name = "jednostka"

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            return queryset.filter(aktualna_jednostka_id=v)
        return queryset

    def lookups(self, request, model_admin):
        return (
            (x.pk, str(x)) for x in Jednostka.objects.all().select_related("wydzial")
        )


class LogEntryFilterBase(SimpleListFilter):
    action_flags = [ADDITION, CHANGE]

    def __init__(self, request, params, model, model_admin):
        self.content_type = ContentType.objects.get_for_model(model)
        super().__init__(
            request=request, params=params, model=model, model_admin=model_admin
        )

    def logentries(self):
        return LogEntry.objects.filter(
            action_flag__in=self.action_flags,
            content_type_id=self.content_type,
        )

    def lookups(self, request, model_admin):
        return (
            (x.pk, str(x))
            for x in BppUser.objects.filter(
                pk__in=self.logentries().values_list("user_id")
            ).only("pk", "username")
        )


class OstatnioZmienionePrzezFilter(LogEntryFilterBase):
    title = "Ostatnio zmieniony przez"
    parameter_name = "ostatnio_zmieniony_przez"

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            res = (
                self.logentries()
                .values("object_id", "content_type_id")
                .annotate(
                    max_action_time=Max("action_time"),
                    max_pk=F("object_id"),
                    max_user=F("user_id"),
                )
                .filter(max_user=v)
                .values_list(Cast("object_id", IntegerField()))
            )

            return queryset.filter(pk__in=res)
        return queryset


class UtworzonePrzezFilter(LogEntryFilterBase):
    title = "Utworzone przez"
    parameter_name = "utworzone_przez"

    action_flags = [ADDITION]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            res = (
                self.logentries()
                .filter(user_id=v)
                .values_list(Cast("object_id", IntegerField()))
            )

            return queryset.filter(pk__in=res)
        return queryset


class AutorZmarlFilter(SimpleNotNullFilter):
    title = "Autor zmarł"
    parameter_name = "zmarl"

    def lookups(self, request, model_admin):
        return [("nie", "autor żyje"), ("tak", "autor zmarł")]

    def queryset(self, request, queryset):
        v = self.value()

        if v == "nie":
            return queryset.filter(zmarl=None)
        elif v == "tak":
            return queryset.exclude(zmarl=None)

        return queryset


class MaEmailFilter(SimpleNotNullFilter):
    title = "Autor ma e-mail"
    parameter_name = "email"


class MaWWWFilter(SimpleNotNullFilter):
    title = "Autor ma WWW"
    parameter_name = "www"


class MaSystemKadrowyIDFilter(SimpleNotNullFilter):
    title = "Autor ma System Kadrowy ID"
    parameter_name = "system_kadrowy_id"


class MaKonferencjeFilter(SimpleNotNullFilter):
    title = "Ma konferencję"
    parameter_name = "konferencja"


class JednostkaNadrzednaFilterForm(forms.Form):
    """Formularz jednopolowy stojący za `JednostkaNadrzednaFilter`.

    Istnieje wyłącznie po to, by przez `forms.ModelChoiceField` przypiąć do
    `ModelSelect2.choices` właściwy `ModelChoiceIterator` — bez tego widget
    nie potrafiłby po przeładowaniu strony wyrenderować etykiety aktualnie
    wybranej jednostki (dostałby tylko jej pk).
    """

    parent = forms.ModelChoiceField(
        queryset=Jednostka.objects.all().select_related("wydzial"),
        required=False,
        label="",
        widget=autocomplete.ModelSelect2(
            url="bpp:jednostka-autocomplete",
            attrs={
                "data-placeholder": "Wybierz jednostkę…",
                "style": "width: 100%;",
            },
        ),
    )


class JednostkaNadrzednaFilter(SimpleListFilter):
    """Filtr changelisty `parent` (kolumna „Jednostka nadrzędna") w JednostkaAdmin.

    Własny, minimalny odpowiednik `admin_auto_filters.AutocompleteFilterFactory`
    (usuniętego w #438 Faza B, III-3a, na życzenie ownera — druga zależność
    dokładałaby DRUGI silnik autocomplete obok już używanego w BPP
    django-autocomplete-light/DAL). Zamiast tego reużywa istniejący DAL-owy
    widok `bpp:jednostka-autocomplete` (ten sam, którego używają
    `admin/core.py`, `admin/autor.py`, `admin/praca_habilitacyjna.py` itd.).
    Wzorowany na `dal_admin_filters.AutocompleteFilter`
    (github.com/shamanu4/dal_admin_filters) — zvendorowany ręcznie jako
    jedna mała klasa + template, BEZ instalowania tego pakietu.

    Powód istnienia niestandardowego rozwiązania: lista jednostek jest zbyt
    duża na zwykły dropdown filtra (`list_filter = ("parent", ...)`
    wygenerowałoby select ze wszystkimi jednostkami w bazie) — potrzebny
    autocomplete AJAX-owy.

    Klucz do działania — DWIE osobne przeszkody:

    1. Media. Changelist Django NIE wciąga automatycznie mediów widgetów
       pól z `list_filter` (w przeciwieństwie do formularza zmiany, gdzie
       `ModelAdmin.media` sumuje media pól formularza) — stąd `media`
       niżej, renderowane jawnie przez template (patrz
       `templates/admin/filters/jednostka_nadrzedna_filter.html`).

    2. Panel filtrów BPP. `src/django_bpp/templates/admin/change_list.html`
       NIE korzysta ze standardowego mechanizmu Django
       (`{% admin_list_filter cl spec %}`, który renderowałby `spec.template`
       przez `get_template(...).render(...)`) — ma własny, HTMX-owy panel
       filtrów, który dla KAŻDEGO filtra po prostu iteruje
       `spec.choices(cl)` i wypisuje listę linków (patrz
       `admin_filter_helpers.get_filter_choices_without_selected`). `spec.template`
       byłby więc martwym kodem w tym projekcie. Zamiast tego ten filtr
       wystawia `custom_widget_template` — atrybut, którego `change_list.html`
       jawnie szuka (`{% if spec.custom_widget_template %}`), by dla TEGO
       jednego filtra wyrenderować nasz template zamiast listy `<a>`.
       Żaden inny filtr w projekcie tego atrybutu nie ma, więc reszta
       panelu (i wszystkie INNE adminy) renderuje się dokładnie jak dotąd.
    """

    title = "Jednostka nadrzędna"
    parameter_name = "parent"
    template = "admin/filters/jednostka_nadrzedna_filter.html"
    custom_widget_template = "admin/filters/jednostka_nadrzedna_filter.html"

    def lookups(self, request, model_admin):
        # SimpleListFilter.has_output() (a więc i obecność filtra w ogóle w
        # sidebarze) wymaga niepustej listy `lookups()` — patrz
        # django.contrib.admin.filters.SimpleListFilter.has_output(). Sama
        # wartość placeholdera nigdy się nie renderuje: wybór idzie AJAX-em
        # przez widget Select2/DAL w naszym `template`, a `choices()` poniżej
        # jest celowo pusty.
        return (("_", "_"),)

    def choices(self, changelist):
        # Domyślna implementacja SimpleListFilter.choices() budowałaby listę
        # linków z `lookups()` — nieużywaną przez nasz template. Metoda musi
        # istnieć (wywołuje ją panel filtrów BPP przez
        # `admin_filter_helpers.get_filter_choices_without_selected`), ale
        # nie ma czego tu wypisywać — wybór idzie AJAX-em przez widget.
        return ()

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(parent_id=value)
        return queryset

    def get_form(self):
        return JednostkaNadrzednaFilterForm(initial={"parent": self.value()})

    def selected_display(self):
        """Etykieta aktualnie wybranej jednostki — do nagłówka filtra.

        Odpowiednik `choice.display` ze standardowych filtrów, którego
        panel BPP oczekuje z `admin_filter_helpers.get_selected_filter_value`
        (patrz tam: sprawdza `spec.selected_display` przed sięgnięciem po
        `spec.choices()`, bo nasze `choices()` jest celowo puste).
        """
        value = self.value()
        if not value:
            return ""
        try:
            return str(Jednostka.objects.get(pk=value))
        except (Jednostka.DoesNotExist, ValueError, TypeError):
            return ""

    def preserved_get_params(self):
        """Pozostałe parametry GET do zachowania przy submicie filtra.

        Bez tego wybór jednostki nadrzędnej zgubiłby inne aktywne filtry
        i wyszukiwanie (formularz filtra submituje przez GET tylko swoje
        własne pole). `p` (numer strony) też pomijamy — zmiana filtra ma
        wracać na pierwszą stronę wyników.
        """
        return [
            (key, value)
            for key, values in self.request.GET.lists()
            for value in values
            if key not in (self.parameter_name, "p")
        ]

    def clear_query_string(self):
        qd = self.request.GET.copy()
        qd.pop(self.parameter_name, None)
        qd.pop("p", None)
        return qd.urlencode()

    @property
    def media(self):
        return self.get_form().media
