import sys

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from import_export.admin import ImportMixin
from mptt.admin import DraggableMPTTAdmin
from mptt.forms import MPTTAdminForm
from reversion_compare.admin import CompareVersionAdmin

from bpp.admin.helpers.djangoql import BppDjangoQLSearchMixin
from bpp.admin.helpers.ror_field import czysc_ror
from bpp.models import Autor_Jednostka, Uczelnia

from ..models.struktura import Jednostka, Jednostka_Rodzic
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .filters import JednostkaNadrzednaFilter, PBN_UID_IDObecnyFilter, WydzialFilter
from .helpers import LimitingFormset
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.site_filtered import SiteFilteredAdminMixin
from .helpers.wersje import HistoriaWersjiMixin
from .jednostka_import import JednostkaImportResource
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin


class Jednostka_RodzicInline(admin.TabularInline):
    model = Jednostka_Rodzic
    # Jednostka_Rodzic ma DWA FK do Jednostka (jednostka, parent) — inline na
    # JednostkaAdmin musi jawnie wskazać po którym się wiąże.
    fk_name = "jednostka"
    extra = 1


class PodjednostkiInline(admin.TabularInline):
    """Read-only lista jednostek PODRZĘDNYCH (bezpośrednich dzieci, ``parent=
    self``) w formularzu JednostkaAdmin -- pokazywana NAD inlinem
    autor-jednostka (Faza B, #438, issue 4).

    W adminie edytujemy jeden poziom drzewa naraz, więc pokazujemy tylko
    bezpośrednie dzieci (nie całe poddrzewo). Inline jest wyłącznie do
    podglądu: bez dodawania/kasowania, pola tylko-do-odczytu, z linkiem do
    formularza zmiany każdej podjednostki. ``fk_name`` jawnie wskazuje
    self-FK ``parent`` (Jednostka ma DWA odwołania do samej siebie:
    ``parent`` w drzewie i denorm ``wydzial``)."""

    model = Jednostka
    fk_name = "parent"
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = "jednostka podrzędna"
    verbose_name_plural = "jednostki podrzędne (bezpośrednie)"
    fields = ("nazwa_link", "skrot", "rodzaj", "aktualna", "widoczna")
    readonly_fields = ("nazwa_link", "skrot", "rodzaj", "aktualna", "widoczna")

    def has_add_permission(self, request, obj=None):
        return False

    def nazwa_link(self, instance):
        if instance.pk is None:
            return ""
        url = reverse("admin:bpp_jednostka_change", args=(instance.pk,))
        return format_html('<a href="{}">{}</a>', url, instance.nazwa)

    nazwa_link.short_description = "Nazwa jednostki"


class Autor_JednostkaForm(forms.ModelForm):
    model = Autor_Jednostka

    class Meta:
        fields = ["autor", "rozpoczal_prace", "zakonczyl_prace", "funkcja"]


class Autor_JednostkaInline(admin.TabularInline):
    form = Autor_JednostkaForm
    model = Autor_Jednostka
    readonly_fields = ["autor"]
    formset = LimitingFormset
    extra = 0


class JednostkaAdminForm(MPTTAdminForm):
    """Walidacja ROR-a przy zapisie jednostki.

    Identyfikator ma sumę kontrolną, więc literówkę widać od razu,
    a nie dopiero po cichym braku ``RORID`` w eksporcie CERIF.

    Dziedziczy z ``MPTTAdminForm``, a NIE z ``forms.ModelForm``. To nie
    jest kosmetyka: ``MPTTModelAdmin`` ustawia ``form = MPTTAdminForm``,
    a ta klasa wycina potomków z listy wyboru ``parent`` i w ``clean()``
    odrzuca rodzica będącego własnym potomkiem. Podmiana na goły
    ``ModelForm`` kasowała tę walidację po MRO i pozwalała zapisać PĘTLĘ
    w drzewie jednostek — czyli rozjechane ``lft``/``rght``/``tree_id``
    i ``get_descendants()`` kręcące się w nieskończoność.
    """

    class Meta:
        model = Jednostka
        fields = ["ror_id"]

    def clean_ror_id(self):
        return czysc_ror(self.cleaned_data.get("ror_id"))


class JednostkaAdmin(
    ImportMixin,
    SiteFilteredAdminMixin,
    BppDjangoQLSearchMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    EksportDanychMixin,
    BaseBppAdminMixin,
    DraggableMPTTAdmin,
    # Historia zmian (FD#587): tuż przed terminalną klasą admina.
    HistoriaWersjiMixin,
    CompareVersionAdmin,
):
    form = JednostkaAdminForm
    uczelnia_field_path = "uczelnia"
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True
    # Eksport (EksportDanychMixin/ExportMixin) bierze resource_classes;
    # import (ImportMixin) dostaje dedykowany resource przez override nizej —
    # oba mixiny domyslnie czytaja TEN SAM atrybut resource_classes.
    resource_classes = [resources.JednostkaResource]

    def po_przywroceniu_wersji(self, request, obj):
        # Wersja niesie rodzica i pola drzewa MPTT z chwili zapisu; po
        # przywróceniu (zapis surowy, z pominięciem MPTT) lft/rght mogą nie
        # pasować do dzisiejszego drzewa — przeliczamy je z rodziców.
        Jednostka._tree_manager.rebuild()

    def zablokuj_przed_przywroceniem(self):
        # Kontrola cyklu czyta rodziców WSZYSTKICH jednostek, a ``rebuild()``
        # i tak zapisze całe drzewo — blokujemy je od razu, żeby równoległe
        # przywrócenie (albo przeniesienie) nie zmieniło rodziców między
        # kontrolą a zapisem.
        list(Jednostka._base_manager.select_for_update().values_list("pk"))

    def przeszkody_przywrocenia(self, obj, wersja):
        # Wersja przywraca dawnego rodzica bez walidacji formularza. Jeśli
        # od tamtej pory drzewo przebudowano (np. dawny rodzic jest dziś
        # PODjednostką tej jednostki), powstałby cykl — gałąź bez korzenia,
        # której ``rebuild()`` nie naprawi.
        rodzic_id = wersja.field_dict.get("parent_id")
        if rodzic_id is None:
            return []
        rodzice = dict(Jednostka._base_manager.values_list("pk", "parent_id"))
        if rodzic_id not in rodzice:
            return [
                "Jednostka nadrzędna z tej wersji już nie istnieje. Ustaw "
                "jednostkę nadrzędną ręcznie w formularzu."
            ]
        odwiedzone = set()
        biezacy = rodzic_id
        while biezacy is not None and biezacy not in odwiedzone:
            if biezacy == obj.pk:
                nazwa = Jednostka._base_manager.get(pk=rodzic_id)
                return [
                    f"W tej wersji jednostką nadrzędną jest „{nazwa}”, która "
                    "jest teraz podjednostką tej jednostki — przywrócenie "
                    f"zapętliłoby strukturę. Najpierw przenieś „{nazwa}” "
                    "w inne miejsce drzewa."
                ]
            odwiedzone.add(biezacy)
            biezacy = rodzice.get(biezacy)
        return []

    def get_import_resource_classes(self, request):
        resource_classes = [JednostkaImportResource]
        self.check_resource_classes(resource_classes)
        return resource_classes

    change_list_template = "admin/grappelli_mptt_change_list.html"
    # ImportMixin + EksportDanychMixin (ExportMixin) jednoczesnie: import_export
    # wybiera `import_export_change_list_template` po MRO, a ImportMixin jest
    # przed ExportMixin -> bez tego renderuje sie szablon TYLKO z importem
    # (przycisk "Eksport" znika). Wymuszamy polaczony szablon import+export;
    # rozszerza on `change_list_template` (grappelli_mptt) jako bazowy, wiec
    # draggable MPTT zostaje zachowany.
    import_export_change_list_template = (
        "admin/import_export/change_list_import_export.html"
    )

    list_display_links = ["indented_title"]

    list_display = [
        "tree_actions",
        "indented_title",
        "skrot",
        "parent_nazwa",
        "uczelnia_skrot",
        "wydzial_skrot",
        "widoczna",
        "rodzaj",
        "wchodzi_do_rankingu_autorow",
        "skupia_pracownikow",
        "pbn_uid_id",
    ]

    list_select_related = [
        "wydzial",
        "rodzaj",
        "uczelnia",
        # kolumna ``parent_nazwa`` czyta ``item.parent.nazwa``
        "parent",
    ]

    def get_queryset(self, request):
        """Wymuś ``list_select_related`` — ChangeList by go tutaj POMINĄŁ.

        ``ChangeList.get_queryset`` aplikuje ``list_select_related``
        warunkowo::

            if not qs.query.select_related:
                qs = self.apply_select_related(qs)

        czyli TYLKO gdy queryset bazowy nie ma jeszcze ŻADNEGO
        ``select_related``. A ``JednostkaManager.get_queryset()`` dokłada
        ``.select_related("wydzial")`` (denormalizowany self-FK), więc
        warunek jest fałszywy i CAŁA deklaracja wyżej przepada — do
        zapytania trafia sam ``wydzial``, bez ``rodzaj`` i ``uczelnia``.

        Efekt był niewidoczny gołym okiem, bo obie relacje i tak są
        dotykane w każdym wierszu (``rodzaj`` to kolumna ``list_display``,
        ``uczelnia`` czyta ``Jednostka.__str__`` sprawdzając
        ``uzywaj_wydzialow``) — po prostu leniwie, per wiersz. Dokładamy je
        wprost; ``select_related`` się scala, więc ``wydzial`` z managera
        nie ginie.

        Regresję pilnuje ``test_admin_select_related.py``: przybija
        niezmiennik „liczba zapytań nie rośnie z liczbą wierszy", więc
        działa na Django 5.2 i nie potrzebuje *fetch modes*. Na gałęzi
        ``django-6.1`` dokłada się do tego ostrzejsza bramka
        ``test_fetch_raise_gate.py`` (tryb ``FETCH_RAISE`` wywala się
        z nazwą pola, gdy changelista dotknie relacji spoza deklaracji).
        """
        qs = super().get_queryset(request)
        return qs.select_related(*self.list_select_related)

    fields = None
    list_filter = (
        WydzialFilter,
        JednostkaNadrzednaFilter,
        "widoczna",
        "nie_eksportuj_przez_api",
        "wchodzi_do_rankingu_autorow",
        "skupia_pracownikow",
        "zarzadzaj_automatycznie",
        "rodzaj",
        "aktualna",
        PBN_UID_IDObecnyFilter,
    )
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]

    inlines = (
        Jednostka_RodzicInline,
        PodjednostkiInline,
        Autor_JednostkaInline,
    )

    autocomplete_fields = ["pbn_uid"]

    readonly_fields = ["wydzial", "aktualna", "ostatnio_zmieniony"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "skrot",
                    "uczelnia",
                    "wydzial",
                    "parent",
                    "aktualna",
                    "pbn_id",
                    "pbn_uid",
                    "rodzaj",
                    "opis",
                    "widoczna",
                    "nie_eksportuj_przez_api",
                    "wchodzi_do_rankingu_autorow",
                    "skupia_pracownikow",
                    "zarzadzaj_automatycznie",
                    "email",
                    "www",
                    "ror_id",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )

    def get_changeform_initial_data(self, request):
        # Zobacz na komentarz do Jednostka.uczelnia.default
        data = super().get_changeform_initial_data(request)
        if "uczelnia" not in data:
            data["uczelnia"] = Uczelnia.objects.get_for_request(request)
        return data

    def changelist_view(self, request, *args, **kwargs):
        self.request = request
        return super().changelist_view(request, *args, **kwargs)

    #
    # Jednostek nie kasuje się wcale (ani do kosza) — patrz
    # ``bpp.models.jednostka.JednostkaNieDoUsuniecia``.
    #

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        actions.pop("delete_selected_tree", None)
        return actions

    def indented_title(self, item):
        """
        Generate a short title for an object, indent it depending on
        the object's depth in the hierarchy.
        """

        # Wysuwaj nazwę jednostki wyłacznie w przypadku, gdy nie filtrujemy listy
        if not self.request.GET.keys():
            return super().indented_title(item)

        return format_html(
            "<div>{}</div>",
            item,
        )

    indented_title.short_description = "Nazwa jednostki"

    def wydzial_skrot(self, item):
        if item.wydzial_id:
            return item.wydzial.skrot

    wydzial_skrot.short_description = "Wydział"

    def uczelnia_skrot(self, item):
        if item.uczelnia_id:
            return item.uczelnia.skrot

    uczelnia_skrot.short_description = "Uczelnia"

    def parent_nazwa(self, item):
        if item.parent_id:
            return item.parent.nazwa

    parent_nazwa.short_description = "Jednostka nadrzędna"

    def get_list_display(self, request):
        if request.GET.keys():
            return self.list_display[1:]
        return self.list_display

    def get_list_filter(self, request):
        # Multi-hosted: superuser widzi jednostki WSZYSTKICH uczelni naraz
        # (SiteFilteredAdminMixin zawęża tylko nie-superuserów), więc bez filtra
        # nie da się ograniczyć listy do jednej uczelni. Dokładamy filtr
        # „uczelnia" (pierwszy) TYLKO gdy w systemie jest >1 uczelnia — na
        # instalacji single-tenant byłby zbędny (jedna wartość do wyboru).
        if Uczelnia.objects.count() > 1:
            return ("uczelnia", *self.list_filter)
        return self.list_filter

    def get_list_per_page(self):
        from django.db import DatabaseError, connection

        # Django evaluates `ModelAdmin.list_per_page` during app-ready
        # system checks (`apps.populate()`), które `manage.py migrate`
        # uruchamia PRZED zastosowaniem migracji. W tym oknie schemat bazy
        # potrafi być starszy niż kod — bail out do wartości domyślnej w
        # każdym takim „schema-lags-code":
        #   * DB nieosiągalna (OperationalError) — fresh clone / CI bez PG,
        #   * tabela `bpp_uczelnia` jeszcze nie istnieje (świeża baza),
        #   * tabela istnieje, ale świeżo dodana, nie-zmigrowana kolumna
        #     (np. `site_id` z multi-hosted) — istniejąca instalacja w
        #     trakcie upgrade'u. Zapytanie rzuca wtedy ProgrammingError;
        #     bez tego guarda `migrate` padał, więc nie dało się zastosować
        #     migracji dodającej kolumnę (deadlock upgrade'u).
        # `DatabaseError` to wspólny rodzic OperationalError/ProgrammingError.
        req = getattr(self, "request", None)
        try:
            if "bpp_uczelnia" not in connection.introspection.table_names():
                return BaseBppAdminMixin.list_per_page
            uczelnia = Uczelnia.objects.get_for_request(req)
        except DatabaseError:
            return BaseBppAdminMixin.list_per_page

        if uczelnia is None:
            return BaseBppAdminMixin.list_per_page

        if uczelnia.sortuj_jednostki_alfabetycznie:
            return BaseBppAdminMixin.list_per_page

        return sys.maxsize

    list_per_page = property(get_list_per_page)


admin.site.register(Jednostka, JednostkaAdmin)
