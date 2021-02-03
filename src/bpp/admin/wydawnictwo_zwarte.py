# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-

from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from mptt.forms import TreeNodeChoiceField

from bpp.admin import helpers
from bpp.admin.filters import (
    CalkowitaLiczbaAutorowFilter,
    DOIUstawioneFilter,
    LiczbaZnakowFilter,
)
from bpp.models import (
    Charakter_Formalny,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych,
)
from bpp.models.konferencja import Konferencja
from bpp.models.seria_wydawnicza import Seria_Wydawnicza

from .actions import ustaw_po_korekcie, ustaw_przed_korekta, ustaw_w_trakcie_korekty
from .core import CommitedModelAdmin, KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .nagroda import NagrodaInline

# Proste tabele


class Wydawnictwo_ZwarteAdmin_Baza(CommitedModelAdmin):
    formfield_overrides = helpers.NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    actions = [ustaw_po_korekcie, ustaw_w_trakcie_korekty, ustaw_przed_korekta]

    list_display = [
        "tytul_oryginalny",
        "wydawnictwo",
        "wydawnictwo_nadrzedne_col",
        "rok",
        "typ_kbn__skrot",
        "charakter_formalny__skrot",
        "liczba_znakow_wydawniczych",
        "ostatnio_zmieniony",
    ]

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe",
        "rok",
        "isbn",
        "id",
        "wydawca__nazwa",
        "wydawca_opis",
        "redakcja",
        "adnotacje",
        "liczba_znakow_wydawniczych",
        "wydawnictwo_nadrzedne__tytul_oryginalny",
        "konferencja__nazwa",
        "liczba_znakow_wydawniczych",
    ]

    list_filter = [
        "status_korekty",
        "recenzowana",
        "typ_kbn",
        "charakter_formalny",
        "informacja_z",
        "jezyk",
        LiczbaZnakowFilter,
        "rok",
        DOIUstawioneFilter,
    ]

    # Usunąć przed wcomitowaniem

    # fieldsets = (
    #     ('Wydawnictwo zwarte', {
    #         'fields':
    #             DWA_TYTULY
    #             + MODEL_ZE_SZCZEGOLAMI
    #             + ('miejsce_i_rok', 'wydawnictwo',)
    #             + MODEL_Z_ISBN
    #             + MODEL_Z_ROKIEM
    #     }),
    #     EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
    #     MODEL_TYPOWANY_FIELDSET,
    #     MODEL_PUNKTOWANY_FIELDSET,
    #     MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
    #     POZOSTALE_MODELE_FIELDSET,
    #     ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET)

    def wydawnictwo_nadrzedne_col(self, obj):
        try:
            return obj.wydawnictwo_nadrzedne.tytul_oryginalny
        except Wydawnictwo_Zwarte.DoesNotExist:
            return ""
        except AttributeError:
            return ""

    wydawnictwo_nadrzedne_col.short_description = "Wydawnictwo nadrzędne"
    wydawnictwo_nadrzedne_col.admin_order_field = (
        "wydawnictwo_nadrzedne__tytul_oryginalny"
    )


class Wydawnictwo_ZwarteForm(helpers.Wycinaj_W_z_InformacjiMixin, forms.ModelForm):
    wydawnictwo_nadrzedne = forms.ModelChoiceField(
        required=False,
        queryset=Wydawnictwo_Zwarte.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawnictwo-nadrzedne-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    wydawca = forms.ModelChoiceField(
        required=False,
        queryset=Wydawca.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawca-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    konferencja = forms.ModelChoiceField(
        required=False,
        queryset=Konferencja.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:konferencja-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    seria_wydawnicza = forms.ModelChoiceField(
        required=False,
        queryset=Seria_Wydawnicza.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:seria-wydawnicza-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    charakter_formalny = TreeNodeChoiceField(
        required=True, queryset=Charakter_Formalny.objects.all()
    )

    status_korekty = helpers.DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"
        widgets = {
            "strony": forms.TextInput(attrs=dict(style="width: 150px")),
            "tom": forms.TextInput(attrs=dict(style="width: 150px")),
        }


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychForm(forms.ModelForm):
    class Meta:
        fields = ["baza", "info"]


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychInline(admin.StackedInline):
    model = Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych
    extra = 0
    form = Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychForm


class Wydawnictwo_ZwarteAdmin(
    KolumnyZeSkrotamiMixin,
    helpers.AdnotacjeZDatamiOrazPBNMixin,
    Wydawnictwo_ZwarteAdmin_Baza,
):
    form = Wydawnictwo_ZwarteForm

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Zwarte_Autor),
        NagrodaInline,
        Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychInline,
        Grant_RekorduInline,
        Element_RepozytoriumInline,
    )

    list_filter = Wydawnictwo_ZwarteAdmin_Baza.list_filter + [
        CalkowitaLiczbaAutorowFilter,
        "openaccess_tryb_dostepu",
        "openaccess_wersja_tekstu",
        "openaccess_licencja",
        "openaccess_czas_publikacji",
    ]

    list_select_related = [
        "charakter_formalny",
        "typ_kbn",
        "wydawnictwo_nadrzedne",
        "wydawca",
    ]

    fieldsets = (
        (
            "Wydawnictwo zwarte",
            {
                "fields": helpers.DWA_TYTULY
                + helpers.MODEL_ZE_SZCZEGOLAMI
                + (
                    "wydawnictwo_nadrzedne",
                    "konferencja",
                    "calkowita_liczba_autorow",
                    "calkowita_liczba_redaktorow",
                    "oznaczenie_wydania",
                    "miejsce_i_rok",
                    "wydawca",
                    "wydawca_opis",
                )
                + helpers.MODEL_Z_ISBN
                + helpers.MODEL_Z_ROKIEM
            },
        ),
        helpers.SERIA_WYDAWNICZA_FIELDSET,
        helpers.EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        helpers.MODEL_TYPOWANY_FIELDSET,
        helpers.MODEL_PUNKTOWANY_FIELDSET,
        helpers.MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        helpers.POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET,
        helpers.ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        helpers.MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
        helpers.OPENACCESS_FIELDSET,
        helpers.PRACA_WYBITNA_FIELDSET,
        helpers.PRZED_PO_LISCIE_AUTOROW_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        super(Wydawnictwo_ZwarteAdmin, self).save_model(request, obj, form, change)
        if (
            obj.rok >= 2017
            and obj.rok <= 2020
            and obj.charakter_formalny.charakter_sloty is None
        ):
            messages.warning(
                request,
                'Punkty dla dyscyplin dla "%s" nie będą liczone, gdyż jest to ani książka, ani rozdział'
                % helpers.link_do_obiektu(obj),
            )
        else:
            helpers.sprobuj_policzyc_sloty(request, obj)


admin.site.register(Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)
