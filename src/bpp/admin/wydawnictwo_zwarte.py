# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-

from dal import autocomplete
from django.contrib import admin
from mptt.forms import TreeNodeChoiceField

from bpp.admin.filters import LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter
from bpp.admin.helpers import *
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, Charakter_Formalny
from bpp.models.konferencja import Konferencja
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from .core import CommitedModelAdmin, generuj_inline_dla_autorow, \
    KolumnyZeSkrotamiMixin
from .nagroda import NagrodaInline


# Proste tabele

class Wydawnictwo_ZwarteAdmin_Baza(CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    list_display = ['tytul_oryginalny', 'wydawnictwo',
                    'wydawnictwo_nadrzedne_col',
                    'rok',
                    'typ_kbn__skrot',
                    'charakter_formalny__skrot',
                    'liczba_znakow_wydawniczych',
                    'ostatnio_zmieniony']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'isbn', 'id',
        'wydawnictwo', 'redakcja', 'adnotacje',
        'liczba_znakow_wydawniczych',
        'wydawnictwo_nadrzedne__tytul_oryginalny',
        'konferencja__nazwa',
        'liczba_znakow_wydawniczych',
    ]

    list_filter = ['status_korekty', 'recenzowana', 'typ_kbn',
                   'charakter_formalny', 'informacja_z', 'jezyk',
                   LiczbaZnakowFilter, 'rok']

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
            return ''
        except AttributeError:
            return ''

    wydawnictwo_nadrzedne_col.short_description = "Wydawnictwo nadrzędne"
    wydawnictwo_nadrzedne_col.admin_order_field = "wydawnictwo_nadrzedne__tytul_oryginalny"


class Wydawnictwo_ZwarteForm(Wycinaj_W_z_InformacjiMixin, forms.ModelForm):
    wydawnictwo_nadrzedne = forms.ModelChoiceField(
        required=False,
        queryset=Wydawnictwo_Zwarte.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:wydawnictwo-nadrzedne-autocomplete',
            attrs=dict(style="width: 746px;")
        )
    )

    konferencja = forms.ModelChoiceField(
        required=False,
        queryset=Konferencja.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:konferencja-autocomplete',
            attrs=dict(style="width: 746px;")
        )
    )

    seria_wydawnicza = forms.ModelChoiceField(
        required=False,
        queryset=Seria_Wydawnicza.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:seria-wydawnicza-autocomplete',
            attrs=dict(style="width: 746px;"),
        )
    )

    charakter_formalny = TreeNodeChoiceField(
        required=True,
        queryset=Charakter_Formalny.objects.all()
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"
        widgets = {
            'strony': forms.TextInput(attrs=dict(style="width: 150px")),
            'tom': forms.TextInput(attrs=dict(style="width: 150px")),
        }


class Wydawnictwo_ZwarteAdmin(KolumnyZeSkrotamiMixin,
                              AdnotacjeZDatamiOrazPBNMixin,
                              Wydawnictwo_ZwarteAdmin_Baza):
    form = Wydawnictwo_ZwarteForm

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Zwarte_Autor),
        NagrodaInline
    )

    list_filter = Wydawnictwo_ZwarteAdmin_Baza.list_filter + [
        CalkowitaLiczbaAutorowFilter,
        'openaccess_tryb_dostepu',
        'openaccess_wersja_tekstu',
        'openaccess_licencja',
        'openaccess_czas_publikacji',
    ]

    list_select_related = ['charakter_formalny', 'typ_kbn',
                           'wydawnictwo_nadrzedne', ]

    fieldsets = (
        ('Wydawnictwo zwarte', {
            'fields':
                DWA_TYTULY
                + MODEL_ZE_SZCZEGOLAMI
                + ('wydawnictwo_nadrzedne',
                   'konferencja',
                   'calkowita_liczba_autorow',
                   'calkowita_liczba_redaktorow',
                   'miejsce_i_rok',
                   'wydawnictwo',)
                + MODEL_Z_ISBN
                + MODEL_Z_ROKIEM
        }),
        SERIA_WYDAWNICZA_FIELDSET,
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET,
        ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        OPENACCESS_FIELDSET,
        PRACA_WYBITNA_FIELDSET)


admin.site.register(Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)
