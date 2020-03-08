# -*- encoding: utf-8 -*-
from decimal import Decimal

from dal import autocomplete
from dal_select2.fields import Select2ListCreateChoiceField
from django import forms
from django.contrib import admin
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms.widgets import HiddenInput

from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.models import (
    Jednostka,
    Autor,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Dyscyplina_Naukowa,
)

# Proste tabele

BaseBppAdmin = admin.ModelAdmin


class CommitedModelAdmin(BaseBppAdmin):
    """Ta klasa jest potrzebna, (XXXżeby działały sygnały post_commit.XXX)

    Ta klasa KIEDYŚ była potrzebna, obecnie niespecjalnie. Aczkolwiek,
    zostawiam ją z przyczyn historycznych, w ten sposób można łatwo
    wyłowić klasy edycyjne, które grzebią COKOLWIEK w cache.
    """

    # Mój dynks do grappelli
    auto_open_collapsibles = True

    def save_formset(self, *args, **kw):
        super(CommitedModelAdmin, self).save_formset(*args, **kw)
        # transaction.commit()


def get_first_typ_odpowiedzialnosci():
    return Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()


def generuj_inline_dla_autorow(baseModel, include_dyscyplina=True):
    class baseModel_AutorFormset(forms.BaseInlineFormSet):
        def clean(self):
            # get forms that actually have valid data
            percent = Decimal("0.00")
            for form in self.forms:
                try:
                    if form.cleaned_data:
                        percent += form.cleaned_data.get(
                            "procent", Decimal("0.00")
                        ) or Decimal("0.00")
                except AttributeError:
                    # annoyingly, if a subform is invalid Django explicity raises
                    # an AttributeError for cleaned_data
                    pass
            if percent > Decimal("100.00"):
                raise forms.ValidationError(
                    "Liczba podanych procent odpowiedzialności przekracza 100.0"
                )

    class baseModel_AutorForm(forms.ModelForm):

        autor = forms.ModelChoiceField(
            queryset=Autor.objects.all(),
            widget=autocomplete.ModelSelect2(url="bpp:autor-autocomplete"),
        )

        jednostka = forms.ModelChoiceField(
            queryset=Jednostka.objects.all(),
            widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
        )

        if include_dyscyplina:
            dyscyplina_naukowa = forms.ModelChoiceField(
                queryset=Dyscyplina_Naukowa.objects.all(),
                widget=autocomplete.ModelSelect2(
                    forward=["autor", "rok"],
                    url="bpp:dyscyplina-naukowa-przypisanie-autocomplete",
                ),
                required=False,
            )

        zapisany_jako = Select2ListCreateChoiceField(
            choice_list=[],
            widget=autocomplete.Select2(
                url="bpp:zapisany-jako-autocomplete", forward=["autor"]
            ),
        )

        typ_odpowiedzialnosci = forms.ModelChoiceField(
            queryset=Typ_Odpowiedzialnosci.objects.all(),
            initial=get_first_typ_odpowiedzialnosci,
        )

        def __init__(self, *args, **kwargs):
            super(baseModel_AutorForm, self).__init__(*args, **kwargs)

            # Ustaw inicjalną wartość dla pola 'afiliuje'
            domyslnie_afiliuje = True
            uczelnia = Uczelnia.objects.first()
            if uczelnia is not None:
                domyslnie_afiliuje = uczelnia.domyslnie_afiliuje
            self.fields["afiliuje"].initial = domyslnie_afiliuje

            # Nowy rekord
            instance = kwargs.get("instance")
            data = kwargs.get("data")
            if not data and not instance:
                # Jeżeli nie ma na czym pracowac
                return

            initial = None

            if instance:
                autor = instance.autor
                initial = instance.zapisany_jako

            if data:
                # "Nowe" dane z formularza przyszły
                zapisany_jako = data.get(kwargs["prefix"] + "-zapisany_jako")
                if not zapisany_jako:
                    return

                try:
                    autor = Autor.objects.get(pk=int(data[kwargs["prefix"] + "-autor"]))
                except Autor.DoesNotExist:

                    class autor:
                        imiona = "TakiAutor"
                        nazwisko = "NieIstnieje"
                        poprzednie_nazwiska = ""

            warianty = warianty_zapisanego_nazwiska(
                autor.imiona, autor.nazwisko, autor.poprzednie_nazwiska
            )
            warianty = list(warianty)

            if initial not in warianty and instance is not None:
                warianty.append(instance.zapisany_jako)

            self.initial["zapisany_jako"] = initial

            self.fields["zapisany_jako"] = Select2ListCreateChoiceField(
                choice_list=list(warianty),
                initial=initial,
                widget=autocomplete.Select2(
                    url="bpp:zapisany-jako-autocomplete", forward=["autor"]
                ),
            )

        class Media:
            js = ["/static/bpp/js/autorform_dependant.js"]

        class Meta:
            fields = [
                "autor",
                "jednostka",
                "typ_odpowiedzialnosci",
                "zapisany_jako",
                "afiliuje",
                "zatrudniony",
                "procent",
                "kolejnosc",
            ]
            model = baseModel
            widgets = {"kolejnosc": HiddenInput}

    baseClass = admin.StackedInline
    extraRows = 0

    from django.conf import settings

    if getattr(settings, "INLINE_DLA_AUTOROW", "stacked") == "tabular":
        baseClass = admin.TabularInline
        extraRows = 1

    class baseModel_AutorInline(baseClass):
        model = baseModel
        extra = extraRows
        form = baseModel_AutorForm
        formset = baseModel_AutorFormset
        sortable_field_name = "kolejnosc"
        sortable_excludes = [
            "typ_odpowiedzialnosci",
            "zapisany_jako",
            "afiliuje",
        ]

    return baseModel_AutorInline


#
# Kolumny ze skrótami
#


class KolumnyZeSkrotamiMixin:
    def charakter_formalny__skrot(self, obj):
        return obj.charakter_formalny.skrot

    charakter_formalny__skrot.short_description = "Char. form."
    charakter_formalny__skrot.admin_order_field = "charakter_formalny__skrot"

    def typ_kbn__skrot(self, obj):
        return obj.typ_kbn.skrot

    typ_kbn__skrot.short_description = "Typ KBN"
    typ_kbn__skrot.admin_order_field = "typ_kbn__skrot"


class RestrictDeletionToAdministracjaGroupMixin:
    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        if "administracja" in [x.name for x in request.user.cached_groups]:
            return admin.ModelAdmin.get_action_choices(self, request, default_choices)
        return []

    def has_delete_permission(self, request, obj=None):
        if "administracja" in [x.name for x in request.user.cached_groups]:
            return admin.ModelAdmin.has_delete_permission(self, request, obj=obj)
        return False


class RestrictDeletionToAdministracjaGroupAdmin(
    RestrictDeletionToAdministracjaGroupMixin, admin.ModelAdmin
):
    pass
