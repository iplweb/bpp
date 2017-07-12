# -*- encoding: utf-8 -*-


from dal import autocomplete
from django import forms
from django.contrib import admin
from django.forms.widgets import HiddenInput



from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.models import Jednostka, Autor, Typ_Odpowiedzialnosci

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
    return Typ_Odpowiedzialnosci.objects.filter(skrot='aut.').first()


def generuj_inline_dla_autorow(baseModel):
    class baseModel_AutorForm(forms.ModelForm):

        autor = forms.ModelChoiceField(
            queryset=Autor.objects.all(),
            widget=autocomplete.ModelSelect2(
                url='bpp:autor-autocomplete')
        )

        jednostka = forms.ModelChoiceField(
            queryset=Jednostka.objects.all(),
            widget=autocomplete.ModelSelect2(
                url='bpp:jednostka-autocomplete')
        )

        zapisany_jako = forms.ChoiceField(
            choices=[],
            widget=autocomplete.Select2(
                url="bpp:zapisany-jako-autocomplete",
                forward=['autor']
            )
        )

        typ_odpowiedzialnosci = forms.ModelChoiceField(
            queryset=Typ_Odpowiedzialnosci.objects.all(),
            initial=get_first_typ_odpowiedzialnosci
        )

        def __init__(self, *args, **kwargs):
            super(baseModel_AutorForm, self).__init__(*args, **kwargs)
            # Nowy rekord
            instance = kwargs.get('instance')
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
                zapisany_jako = data.get(kwargs['prefix'] + '-zapisany_jako')
                if not zapisany_jako:
                    return

                autor = Autor.objects.get(pk=int(
                    data[kwargs['prefix'] + '-autor']))

            warianty = warianty_zapisanego_nazwiska(
                autor.imiona,
                autor.nazwisko,
                autor.poprzednie_nazwiska)
            warianty = list(warianty)

            if initial not in warianty:
                warianty.append(instance.zapisany_jako)

            self.initial['zapisany_jako'] = initial

            self.fields['zapisany_jako'] = forms.ChoiceField(
                choices=list(zip(warianty, warianty)),
                initial=initial,
                widget=autocomplete.Select2(
                    url="bpp:zapisany-jako-autocomplete",
                    forward=['autor']
                )
            )

        class Media:
            js = ["/static/bpp/js/autorform_dependant.js"]

        class Meta:
            fields = ["autor", "jednostka", "typ_odpowiedzialnosci",
                      "zapisany_jako",
                      "zatrudniony", "kolejnosc"]
            model = baseModel
            widgets = {
                'kolejnosc': HiddenInput
            }

    class baseModel_AutorInline(admin.TabularInline):
        model = baseModel
        extra = 0
        form = baseModel_AutorForm
        sortable_field_name = "kolejnosc"

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