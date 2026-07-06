# Proste tabele
from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.db.models import Count, F

from bpp.admin.helpers.djangoql import BppDjangoQLSearchMixin
from bpp.models.zrodlo import Redakcja_Zrodla
from pbn_api.models import Journal

from ..models import (  # Publikacja_Habilitacyjna
    Autor,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Zrodlo,
)
from .core import BaseBppAdminMixin
from .filters import (
    MaPublikacjeFilter,
    MniswIdObecnyFilter,
    PBN_UID_IDObecnyFilter,
)
from .helpers.fieldsets import ADNOTACJE_FIELDSET, MODEL_PUNKTOWANY_Z_KWARTYLAMI_BAZA
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.widgets import CHARMAP_SINGLE_LINE, COMMA_DECIMAL_FIELD_OVERRIDE

# Rozmiar paczki kasowania w akcji admina „Usuń źródła bez publikacji".
# Kasujemy wsadowo (nie jednym przebiegiem), bo request admina na dziesiątki
# tysięcy źródeł potrafi przekroczyć limit czasu — a każda paczka commituje się
# osobno (akcja nie jest atomic, ATOMIC_REQUESTS=False), więc padnięcie w połowie
# NIE cofa całego postępu: już skasowane paczki zostają, a ponowne uruchomienie
# akcji dokańcza resztę. Dla naprawdę wielkich zbiorów i tak preferowana jest
# komenda `manage.py usun_zrodla_bez_publikacji` (bez limitu czasu requestu).
USUN_ZRODLA_BATCH = 5000

# Źródła indeksowane


class Punktacja_ZrodlaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].help_text = ""


class Punktacja_ZrodlaInline(admin.TabularInline):
    model = Punktacja_Zrodla
    form = Punktacja_ZrodlaForm
    formfield_overrides = COMMA_DECIMAL_FIELD_OVERRIDE
    fields = ("rok",) + MODEL_PUNKTOWANY_Z_KWARTYLAMI_BAZA
    extra = 1


class Redakcja_ZrodlaForm(forms.ModelForm):
    redaktor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-autocomplete"),
    )

    model = Redakcja_Zrodla


class Redakcja_ZrodlaInline(admin.TabularInline):
    model = Redakcja_Zrodla
    extra = 1
    form = Redakcja_ZrodlaForm

    class Meta:
        fields = "__all__"


class Dyscyplina_ZrodlaInline(admin.TabularInline):
    model = Dyscyplina_Zrodla
    classes = ["grp-collapse grp-closed grp-never-open-automatically"]
    extra = 1

    class Meta:
        fields = [
            "rok",
            "dyscyplina",
        ]


class ZrodloForm(forms.ModelForm):
    pbn_uid = forms.ModelChoiceField(
        label="Odpowiednik w PBN",
        required=False,
        queryset=Journal.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:journal-autocomplete",
            attrs={"class": "bpp-autocomplete-wide"},
        ),
    )

    class Meta:
        model = Zrodlo
        fields = [
            "adnotacje",
            "issn",
            "e_issn",
            "nazwa",
            "skrot",
            "rodzaj",
            "nazwa_alternatywna",
            "skrot_nazwy_alternatywnej",
            "zasieg",
            "www",
            "doi",
            "poprzednia_nazwa",
            "openaccess_tryb_dostepu",
            "openaccess_licencja",
            "jezyk",
            "wydawca",
            "pbn_uid",
        ]
        widgets = {
            "nazwa": CHARMAP_SINGLE_LINE,
            "skrot": CHARMAP_SINGLE_LINE,
            "nazwa_alternatywna": CHARMAP_SINGLE_LINE,
            "skrot_nazwy_alternatywnej": CHARMAP_SINGLE_LINE,
            "poprzednia_nazwa": CHARMAP_SINGLE_LINE,
        }


class ZrodloAdmin(
    BppDjangoQLSearchMixin, ZapiszZAdnotacjaMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    form = ZrodloForm

    fields = None
    inlines = (Punktacja_ZrodlaInline, Redakcja_ZrodlaInline, Dyscyplina_ZrodlaInline)
    search_fields = [
        "nazwa",
        "skrot",
        "nazwa_alternatywna",
        "skrot_nazwy_alternatywnej",
        "issn",
        "e_issn",
        "www",
        "poprzednia_nazwa",
        "doi",
        "pbn_uid__pk",
    ]

    autocomplete_fields = ["pbn_uid"]
    list_display = [
        "nazwa",
        "skrot",
        "rodzaj",
        "www",
        "issn",
        "e_issn",
        "pbn_uid_id",
        "mnisw_id_display",
        "liczba_prac_display",
    ]
    list_filter = [
        "rodzaj",
        "zasieg",
        "jezyk",
        "openaccess_tryb_dostepu",
        "openaccess_licencja",
        PBN_UID_IDObecnyFilter,
        MniswIdObecnyFilter,
        MaPublikacjeFilter,
    ]
    list_select_related = ["openaccess_licencja", "rodzaj"]

    actions = ["usun_zrodla_bez_publikacji_action"]

    @admin.action(
        description="Usuń zaznaczone źródła BEZ publikacji (bez potwierdzenia)"
    )
    def usun_zrodla_bez_publikacji_action(self, request, queryset):
        """Kasuje zaznaczone źródła, ale WYŁĄCZNIE te bez żadnej publikacji.

        Działa na queryset (przy „zaznacz wszystkie pasujące" / select_across
        wysyłane są tylko PK ze strony, więc nie ma problemu z limitem pól
        POST). Omija zbieranie powiązań (collector) — kasuje wsadowo, więc
        radzi sobie z dziesiątkami tysięcy źródeł. Źródła z publikacjami są
        pomijane (bezpiecznik)."""
        selected = list(queryset.values_list("pk", flat=True))
        do_usuniecia = list(
            Zrodlo.objects.filter(
                pk__in=selected, wydawnictwo_ciagle__isnull=True
            ).values_list("pk", flat=True)
        )

        # Kasuj w paczkach po USUN_ZRODLA_BATCH — każda paczka commituje się
        # osobno, więc timeout requestu na dużym zbiorze nie cofa całego postępu
        # (patrz komentarz przy stałej). Kolektor kaskady liczony jest raz na
        # paczkę — świadomy kompromis: odporność na timeout ważniejsza tu niż
        # ostatnie sekundy czasu.
        for i in range(0, len(do_usuniecia), USUN_ZRODLA_BATCH):
            chunk = do_usuniecia[i : i + USUN_ZRODLA_BATCH]
            Zrodlo.objects.filter(pk__in=chunk).delete()
        deleted = len(do_usuniecia)

        skipped = len(selected) - len(do_usuniecia)
        msg = f"Usunięto {deleted} źródeł bez publikacji."
        if skipped:
            msg += f" Pominięto {skipped} (mają publikacje)."
        self.message_user(request, msg, level=messages.SUCCESS)

    def get_queryset(self, request):
        # _liczba_prac: liczba publikacji (tylko Wydawnictwo_Ciagle ma FK do
        # Zrodlo). distinct=True chroni licznik przed zawyżeniem, gdyby
        # wyszukiwarka DjangoQL dorzuciła drugi multi-valued JOIN.
        # _mnisw_id: annotacja pojedynczej kolumny mniswId przez JOIN do
        # Journal — tańsze niż select_related("pbn_uid"), które ciągnęłoby
        # ciężki blob JSON Journal.versions dla każdego wiersza listy.
        return (
            super()
            .get_queryset(request)
            .annotate(
                _liczba_prac=Count("wydawnictwo_ciagle", distinct=True),
                _mnisw_id=F("pbn_uid__mniswId"),
            )
        )

    @admin.display(description="mniswID", ordering="_mnisw_id")
    def mnisw_id_display(self, obj):
        return obj._mnisw_id

    @admin.display(description="Publikacje", ordering="_liczba_prac")
    def liczba_prac_display(self, obj):
        return obj._liczba_prac

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "skrot",
                    "rodzaj",
                    "nazwa_alternatywna",
                    "skrot_nazwy_alternatywnej",
                    "issn",
                    "e_issn",
                    "www",
                    "doi",
                    "pbn_uid",
                    "zasieg",
                    "poprzednia_nazwa",
                    "jezyk",
                    "wydawca",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
        (
            "OpenAccess",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "openaccess_tryb_dostepu",
                    "openaccess_licencja",
                ),
            },
        ),
    )


admin.site.register(Zrodlo, ZrodloAdmin)
