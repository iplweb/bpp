# -*- encoding: utf-8 -*-

import autocomplete_light

from bpp.models import Autor, Jednostka, Zrodlo, Wydawnictwo_Zwarte
from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from autocomplete_light.shortcuts import AutocompleteModelTemplate, \
    AutocompleteTemplate, register

class AutocompleteAutor(AutocompleteModelTemplate):
    model = 'autor'  # potrzebny, zeby template wyrenderowało klikalny link dobrze
    autocomplete_js_attributes = {'placeholder': 'autor...'}
    limit_choices = 10

    def choices_for_request(self):
        q = self.request.GET.get('q', '').encode('utf-8')
        return Autor.objects.fulltext_filter(q)[0:self.limit_choices]


class AutorMultiseek(AutocompleteModelTemplate):
    choices = Autor.objects
    limit_choices = 10

    def choices_for_request(self):
        q = self.request.GET.get('q', '').encode('utf-8')
        return self.choices.fulltext_filter(q)

register(
    Autor, AutorMultiseek,
    search_fields=('nazwisko', 'imiona'),
    name="AutorMultiseek")

register(
    Autor, AutocompleteAutor, search_fields=('nazwisko',),
    choice_template="autocompletes/admin.html")


class AutocompleteJednostka(AutocompleteModelTemplate):
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


register(
    Jednostka, AutocompleteJednostka,
    search_fields=('nazwa',),
    name="JednostkaMultiseek",
    choice_template="autocompletes/jednostka.html")

register(
    Jednostka, AutocompleteJednostka,
    search_fields=('nazwa',),
    choice_template="autocompletes/admin.html")


class AutocompleteJednostkaWidoczna(AutocompleteJednostka):
    choices = Jednostka.objects.filter(widoczna=True)


register(
    Jednostka, AutocompleteJednostkaWidoczna,
    search_fields=('nazwa',),
    name="RaportyJednostkaWidoczna",
    choice_template="autocompletes/jednostka.html")


class AutocompleteZrodlo(AutocompleteModelTemplate):
    model = 'zrodlo'
    limit_choices = 7
    pass


register(
    Zrodlo, AutocompleteZrodlo,
    search_fields=('nazwa', 'poprzednia_nazwa', 'nazwa_alternatywna', 'skrot', 'skrot_nazwy_alternatywnej'),
    name="ZrodloMultiseek",
    choice_template="autocompletes/zrodlo.html")

register(
    Zrodlo, AutocompleteZrodlo,
    search_fields=('nazwa', 'poprzednia_nazwa', 'nazwa_alternatywna', 'skrot', 'skrot_nazwy_alternatywnej'),
    autocomplete_js_attributes={'placeholder': u'źródło...'},
    choice_template="autocompletes/admin.html")


class AutocompleteZapisaneNazwiska(AutocompleteTemplate):
    autocomplete_js_attributes = {'placeholder': 'zapisany...'}

    def choices_for_request(self):
        autor_id = self.request.GET.get('autor_id')
        if autor_id is None:
            return ['(... może najpierw wybierz autora)']

        try:
            autor_id = int(autor_id)
            a = Autor.objects.get(pk=autor_id)
        except (KeyError, ValueError):
            return []
        return warianty_zapisanego_nazwiska(a.imiona, a.nazwisko,
                                            a.poprzednie_nazwiska)


register(AutocompleteZapisaneNazwiska)


class AutocompleteWydawnictwo_Zwarte(
    AutocompleteModelTemplate):
    model = 'wydawnictwo_zwarte'


register(
    Wydawnictwo_Zwarte, AutocompleteWydawnictwo_Zwarte,
    search_fields=('tytul_oryginalny', 'tytul'),
    autocomplete_js_attributes={'placeholder': u'wydawnictwo zwarte...'},
    choice_template="wydawnictwo_zwarte_choice.html")


class AutocompleteCacheTytul(AutocompleteModelTemplate):
    limit_choices = 10
    model = 'rekord'

#
# register(
#     Cache, AutocompleteCacheTytul,
#     search_fields=('tytul_oryginalny', 'tytul'),
#     autocomplete_js_attributes={'placeholder': u'tytuł publikacji...'},
#     choice_template=None)
