from dal import autocomplete
from dal.forms import FutureModelForm
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import QuerySetSequenceSelect2
from django import forms
from django.contrib import admin
from django.forms.widgets import HiddenInput
from queryset_sequence import QuerySetSequence
from taggit.forms import TextareaTagWidget

from bpp.models import (  # Publikacja_Habilitacyjna
    Autor,
    Jednostka,
    Patent,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from dspace_api.admin_mixins import DSpaceLinkAdminMixin

from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .helpers.constance_field_mixin import ConstanceScoringFieldsMixin
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
from .helpers.mixins import (
    BppSoftDeleteAdminMixin,
    DomyslnyStatusKorektyMixin,
    Wycinaj_W_z_InformacjiMixin,
)
from .praca_doktorska import Praca_Doktorska_Habilitacyjna_Admin_Base

#
# Praca Habilitacyjna
#
#
from .wydawnictwo_ciagle import CleanDOIWWWPublicWWWMixin
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychZFormatowanieMixin, ExportActionsMixin

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
            attrs={"class": "bpp-autocomplete-wide"},
        ),
    )

    class Meta:
        model = Publikacja_Habilitacyjna
        widgets = {"kolejnosc": HiddenInput}
        # `publikacja` is a GenericForeignKey on the model (non-editable).
        # Django 5.0+ refuses to list non-editable fields in Meta.fields, so
        # we rely on the class-level `publikacja` declaration above instead.
        fields = ["kolejnosc"]


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

    def clean_autor(self):
        """Jeden autor — jedna ŻYWA praca habilitacyjna.

        Do fazy 03 pilnował tego `validate_unique()`, bo `Praca_Habilitacyjna.
        autor` było `OneToOneField`. Faza 03 zamieniła je na `ForeignKey`
        z warunkowym `phab_uniq_autor_zywy` (żeby habilitacja w koszu nie
        blokowała scalania autorów), a to przenosi walidację do
        `Model.validate_constraints()` — który dla constraintu z `condition`
        CICHO POMIJA sprawdzenie, gdy pole warunku (`deleted_at`) jest
        wykluczone z walidacji. A jest: `_get_validation_exclusions()` wyklucza
        wszystko spoza `Meta.fields`, a te admin nadpisuje spłaszczonymi
        `fieldsets`.

        `bpp/admin/core.py` obchodzi to ukrytym polem `deleted_at` na liście
        `fields`. Tam to działa, bo chodzi o inline; tutaj `fieldsets` sterują
        renderowaniem, więc pole wyprodukowałoby widoczny, pusty wiersz
        „Deleted at" w formularzu. Stąd jawne sprawdzenie — czytelniejsze niż
        walka z wykluczeniami, i daje komunikat przy właściwym polu.

        Ograniczenie w bazie zostaje ostateczną gwarancją (to jest walidacja
        formularza, nie blokada wyścigu).
        """
        autor = self.cleaned_data["autor"]

        istniejace = Praca_Habilitacyjna.objects.filter(autor=autor)
        if self.instance.pk is not None:
            istniejace = istniejace.exclude(pk=self.instance.pk)

        if istniejace.exists():
            raise forms.ValidationError("Ten autor ma już pracę habilitacyjną.")

        return autor

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = [
            "tytul_oryginalny",
            "tytul",
            "informacje",
            "szczegoly",
            "uwagi",
            "slowa_kluczowe",
            "slowa_kluczowe_eng",
            "strony",
            "tom",
            "oznaczenie_wydania",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
            "autor",
            "jednostka",
            "isbn",
            "e_isbn",
            "rok",
            "www",
            "dostep_dnia",
            "public_www",
            "public_dostep_dnia",
            "pubmed_id",
            "pmc_id",
            "doi",
            "liczba_cytowan",
            "numer_odbitki",
            "jezyk",
            "jezyk_alt",
            "jezyk_orig",
            "typ_kbn",
            "punkty_kbn",
            "impact_factor",
            "index_copernicus",
            "punktacja_snip",
            "punktacja_wewnetrzna",
            "weryfikacja_punktacji",
            "informacja_z",
            "status_korekty",
            "recenzowana",
            "adnotacje",
            "nie_eksportuj_przez_api",
            "opl_pub_cost_free",
            "opl_pub_research_potential",
            "opl_pub_research_or_development_projects",
            "opl_pub_other",
            "opl_pub_amount",
        ]
        widgets = {
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class Praca_HabilitacyjnaResource(resources.Wydawnictwo_ResourceBase):
    class Meta:
        model = Praca_Habilitacyjna
        exclude = resources.WYDAWNICTWO_TYPOWE_EXCLUDES
        export_order = resources.WYDAWNICTWO_TYPOWY_EXPORT_ORDER


class Praca_HabilitacyjnaAdmin(
    DSpaceLinkAdminMixin,
    ConstanceScoringFieldsMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    # OSTATNI przed baza terminalna — patrz docstring BppSoftDeleteAdminMixin.
    BppSoftDeleteAdminMixin,
    Praca_Doktorska_Habilitacyjna_Admin_Base,
):
    resource_classes = [Praca_HabilitacyjnaResource]
    bibtex_resource_class = resources.Praca_HabilitacyjnaBibTeXResource

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
