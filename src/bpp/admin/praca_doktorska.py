# -*- encoding: utf-8 -*-

from dal import autocomplete
from django.contrib import admin

from .core import CommitedModelAdmin
from .helpers import *
from ..models import Jednostka, Autor, Praca_Doktorska

# Proste tabele


DOKTORSKA_FIELDS = (
    DWA_TYTULY
    + MODEL_ZE_SZCZEGOLAMI
    + (
        "oznaczenie_wydania",
        "miejsce_i_rok",
        "wydawca",
        "wydawca_opis",
        "autor",
        "jednostka",
        "promotor",
    )
    + MODEL_Z_ISBN
    + MODEL_Z_ROKIEM
)


class Praca_Doktorska_Habilitacyjna_Admin_Base(
    AdnotacjeZDatamiMixin, CommitedModelAdmin
):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    list_display = [
        "tytul_oryginalny",
        "autor",
        "jednostka",
        "wydawca",
        "wydawca_opis",
        "typ_kbn",
        "ostatnio_zmieniony",
    ]
    list_select_related = [
        "autor",
        "autor__tytul",
        "jednostka",
        "wydawca",
        "jednostka__wydzial",
        "typ_kbn",
    ]

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe",
        "rok",
        "www",
        "wydawca_opis",
        "wydawca__nazwa",
        "redakcja",
        "autor__tytul__nazwa",
        "jednostka__nazwa",
        "adnotacje",
        "id",
    ]

    list_filter = ["status_korekty", "recenzowana", "typ_kbn"]


class Praca_DoktorskaForm(Wycinaj_W_z_InformacjiMixin, forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-z-uczelni-autocomplete"),
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    promotor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-z-uczelni-autocomplete"),
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        model = Praca_Doktorska
        fields = "__all__"


class Praca_DoktorskaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    form = Praca_DoktorskaForm

    fieldsets = (
        ("Praca doktorska", {"fields": DOKTORSKA_FIELDS}),
        EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET,
    )


admin.site.register(Praca_Doktorska, Praca_DoktorskaAdmin)
