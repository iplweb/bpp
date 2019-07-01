from django.contrib import admin

from bpp.models.patent import Patent, Patent_Autor
from .core import generuj_inline_dla_autorow
from .helpers import *
from .wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin_Baza


class Patent_Form(Wycinaj_W_z_InformacjiMixin, forms.ModelForm):
    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"


class Patent_Admin(AdnotacjeZDatamiMixin, Wydawnictwo_ZwarteAdmin_Baza):
    inlines = (generuj_inline_dla_autorow(Patent_Autor, include_dyscyplina=False),)

    list_display = ['tytul_oryginalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'adnotacje', 'id', ]

    list_filter = ['status_korekty', 'recenzowana', ]

    form = Patent_Form

    fieldsets = (
        ('Patent', {
            'fields':
                ('tytul_oryginalny',)
                + MODEL_ZE_SZCZEGOLAMI
                + ('wydzial',
                   'rodzaj_prawa',
                   'data_zgloszenia',
                   'numer_zgloszenia',
                   'data_decyzji',
                   'numer_prawa_wylacznego',
                   'wdrozenie')
                + MODEL_Z_ROKIEM
                + MODEL_Z_WWW
        }),
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET)


admin.site.register(Patent, Patent_Admin)
