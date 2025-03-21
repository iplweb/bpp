from dal import autocomplete
from dal.forms import FutureModelForm
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import QuerySetSequenceSelect2
from django import forms
from django.forms.widgets import HiddenInput
from queryset_sequence import QuerySetSequence
from taggit.forms import TextareaTagWidget

from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .helpers.fieldsets import (
    ADNOTACJE_Z_DATAMI_FIELDSET,
    DWA_TYTULY,
    EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET,
    MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
    MODEL_PUNKTOWANY_FIELDSET,
    MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
    MODEL_Z_ISBN,
    MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    MODEL_Z_ROKIEM,
    MODEL_ZE_SZCZEGOLAMI,
    POZOSTALE_MODELE_FIELDSET,
)
from .helpers.mixins import DomyslnyStatusKorektyMixin, Wycinaj_W_z_InformacjiMixin
from .praca_doktorska import Praca_Doktorska_Habilitacyjna_Admin_Base

#
# Praca Habilitacyjna
#
#
from .wydawnictwo_ciagle import CleanDOIWWWPublicWWWMixin

from django.contrib import admin

from bpp.models import (  # Publikacja_Habilitacyjna
    Autor,
    Jednostka,
    Patent,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna

HABILITACYJNA_FIELDS = (
    DWA_TYTULY
    + MODEL_ZE_SZCZEGOLAMI
    + (
        "oznaczenie_wydania",
        "miejsce_i_rok",
        "wydawca",
        "wydawca_opis",
        "autor",
        "jednostka",
    )
    + MODEL_Z_ISBN
    + MODEL_Z_ROKIEM
)


class Publikacja_HabilitacyjnaForm(
    Wycinaj_W_z_InformacjiMixin, CleanDOIWWWPublicWWWMixin, FutureModelForm
):
    publikacja = QuerySetSequenceModelField(
        queryset=QuerySetSequence(
            Wydawnictwo_Zwarte.objects.all(),
            Wydawnictwo_Ciagle.objects.all(),
            Patent.objects.all(),
        ),
        required=True,
        widget=QuerySetSequenceSelect2(
            "bpp:podrzedna-publikacja-habilitacyjna-autocomplete",
            forward=["autor"],
            attrs=dict(style="width: 764px;"),
        ),
    )

    class Meta:
        model = Publikacja_Habilitacyjna
        widgets = {"kolejnosc": HiddenInput}
        fields = ["publikacja", "kolejnosc"]


class Publikacja_Habilitacyjna_Inline(admin.TabularInline):
    model = Publikacja_Habilitacyjna
    form = Publikacja_HabilitacyjnaForm
    extra = 1
    sortable_field_name = "kolejnosc"


class Praca_HabilitacyjnaForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-z-uczelni-autocomplete"),
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"
        widgets = {
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class Praca_HabilitacyjnaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    inlines = [
        Publikacja_Habilitacyjna_Inline,
    ]

    form = Praca_HabilitacyjnaForm

    fieldsets = (
        ("Praca habilitacyjna", {"fields": HABILITACYJNA_FIELDS}),
        EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET,
        MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
        MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    )

    inlines = (Grant_RekorduInline, Element_RepozytoriumInline)


admin.site.register(Praca_Habilitacyjna, Praca_HabilitacyjnaAdmin)
