# -*- encoding: utf-8 -*-

from dal import autocomplete
from dal.forms import FutureModelForm
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import QuerySetSequenceSelect2
from django import forms
from django.contrib import admin
from django.forms.widgets import HiddenInput
from queryset_sequence import QuerySetSequence

from bpp.admin.helpers import *
from bpp.models import (
    Jednostka,
    Autor,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Praca_Habilitacyjna,
    Patent,
)  # Publikacja_Habilitacyjna
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from .praca_doktorska import Praca_Doktorska_Habilitacyjna_Admin_Base


#
# Praca Habilitacyjna
#
#

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


class Publikacja_HabilitacyjnaForm(Wycinaj_W_z_InformacjiMixin, FutureModelForm):
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
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET,
    )


admin.site.register(Praca_Habilitacyjna, Praca_HabilitacyjnaAdmin)
