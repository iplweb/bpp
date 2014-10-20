# -*- encoding: utf-8 -*-

import autocomplete_light
from bpp.models import Autor, Jednostka, Zrodlo, Wydawnictwo_Zwarte
from bpp.views import zapytaj_o_autora
from bpp.jezyk_polski import warianty_zapisanego_nazwiska


class AutocompleteAutor(autocomplete_light.AutocompleteModelTemplate):
    model = 'autor'  # potrzebny, zeby template wyrenderowało klikalny link dobrze
    autocomplete_js_attributes = {'placeholder': 'autor...'}
    limit_choices = 10

    def choices_for_request(self):
        q = self.request.GET.get('q', '')
        return Autor.objects.fulltext_filter(q)[0:self.limit_choices]


class AutorMultiseek(autocomplete_light.AutocompleteModelTemplate):
    model = 'autor'
    limit_choices = 10

    def choices_for_request(self):
        q = self.request.GET.get('q', '')
        return self.choices.fulltext_filter(q)

autocomplete_light.register(
    Autor, AutorMultiseek,
    search_fields=('nazwisko', 'imiona'),
    name="AutorMultiseek")

autocomplete_light.register(
    Autor, AutocompleteAutor, search_fields=('nazwisko',),
    choice_template="autocompletes/admin.html")


class AutocompleteJednostka(autocomplete_light.AutocompleteModelTemplate):
    limit_choices = 10
    model = 'jednostka'  # potrzebny, zeby template wyrenderowało klikalny link dobrze
    autocomplete_js_attributes = {'placeholder': 'jednostka...'}
    choices = Jednostka.objects.filter() # widoczna=True)

    def choices_for_request(self):
        q = self.request.GET.get('q', '')
        autor_id = self.request.GET.get('autor_id', None)
        if autor_id:
            choices = Autor.objects.get(pk=autor_id).jednostki.all()
        else:
            choices = self.choices.all()
        if q:
            choices = choices.filter(nazwa__icontains=q)
        return self.order_choices(choices)[0:self.limit_choices]


autocomplete_light.register(
    Jednostka, AutocompleteJednostka,
    search_fields=('nazwa',),
    name="JednostkaMultiseek", choice_template="autocompletes/jednostka.html")

autocomplete_light.register(
    Jednostka, AutocompleteJednostka,
    search_fields=('nazwa',),
    choice_template="autocompletes/admin.html")


class AutocompleteZrodlo(autocomplete_light.AutocompleteModelTemplate):
    model = 'zrodlo'
    limit_choices = 7
    pass


autocomplete_light.register(
    Zrodlo, AutocompleteZrodlo,
    search_fields=('nazwa', 'poprzednia_nazwa', 'alternatywna_nazwa', 'skrot', 'skrot_nazwy_alternatywnej'),
    name="ZrodloMultiseek",
    choice_template="autocompletes/zrodlo.html")

autocomplete_light.register(
    Zrodlo, AutocompleteZrodlo,
    search_fields=('nazwa', 'poprzednia_nazwa', 'alternatywna_nazwa', 'skrot', 'skrot_nazwy_alternatywnej'),
    autocomplete_js_attributes={'placeholder': u'źródło...'},
    choice_template="autocompletes/admin.html")


class AutocompleteZapisaneNazwiska(autocomplete_light.AutocompleteTemplate):
    autocomplete_js_attributes = {'placeholder': 'zapisany...'}

    def choices_for_request(self):
        try:
            autor_id = int(self.request.GET.get('autor_id'))
            a = Autor.objects.get(pk=autor_id)
        except (KeyError, ValueError):
            return []
        return warianty_zapisanego_nazwiska(a.imiona, a.nazwisko,
                                            a.poprzednie_nazwiska)


autocomplete_light.register(AutocompleteZapisaneNazwiska)


class AutocompleteWydawnictwo_Zwarte(
    autocomplete_light.AutocompleteModelTemplate):
    model = 'wydawnictwo_zwarte'


autocomplete_light.register(
    Wydawnictwo_Zwarte, AutocompleteWydawnictwo_Zwarte,
    search_fields=('tytul_oryginalny', 'tytul'),
    autocomplete_js_attributes={'placeholder': u'wydawnictwo zwarte...'},
    choice_template="wydawnictwo_zwarte_choice.html")


class AutocompleteCacheTytul(autocomplete_light.AutocompleteModelTemplate):
    limit_choices = 10
    model = 'rekord'

#
# autocomplete_light.register(
#     Cache, AutocompleteCacheTytul,
#     search_fields=('tytul_oryginalny', 'tytul'),
#     autocomplete_js_attributes={'placeholder': u'tytuł publikacji...'},
#     choice_template=None)
