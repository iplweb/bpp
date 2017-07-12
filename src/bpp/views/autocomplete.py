# -*- encoding: utf-8 -*-
import json

from dal import autocomplete
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django import http
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models.query_utils import Q
from queryset_sequence import QuerySetSequence

from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.lookups import SearchQueryStartsWith
from bpp.models import Jednostka
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent, Patent_Autor
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.profile import BppUser
from bpp.models.system import Charakter_Formalny
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, \
    Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, \
    Wydawnictwo_Zwarte_Autor
from bpp.models.zrodlo import Zrodlo


class Wydawnictwo_NadrzedneAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        roz = Charakter_Formalny.objects.get(skrot="ROZ")
        rozs = Charakter_Formalny.objects.get(skrot="ROZS")

        qs = Wydawnictwo_Zwarte.objects.all()
        qs = qs.exclude(charakter_formalny=roz)
        qs = qs.exclude(charakter_formalny=rozs)

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class JednostkaAutocomplete(autocomplete.Select2QuerySetView):
    qset = Jednostka.objects.all()

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(nazwa__icontains=self.q)
        return qs

class KonferencjaAutocomplete(autocomplete.Select2QuerySetView):
    qset = Konferencja.objects.all()

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(nazwa__icontains=self.q)
        return qs


class WidocznaJednostkaAutocomplete(JednostkaAutocomplete):
    qset = Jednostka.objects.filter(widoczna=True)


class ZrodloAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Zrodlo.objects.all()
        if self.q:
            for token in [x.strip() for x in self.q.split(" ") if x.strip()]:
                qs = qs.filter(
                    Q(nazwa__icontains=token) |
                    Q(poprzednia_nazwa__icontains=token) |
                    Q(nazwa_alternatywna__icontains=token) |
                    Q(skrot__istartswith=token) |
                    Q(skrot_nazwy_alternatywnej__istartswith=token)
                )
        return qs


class AutorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Autor.objects.all()
        if self.q:
            query = SearchQueryStartsWith(
                "&".join([x.strip() + ":*" for x in self.q.split()]),
                config="bpp_nazwy_wlasne")

            qs = qs.filter(search=query)
        return qs


class AutorZUczelniAutocopmlete(AutorAutocomplete):
    pass


class GlobalNavigationAutocomplete(Select2QuerySetSequenceView):
    paginate_by = 20

    def get_queryset(self):
        if not self.q:
            return []

        querysets = []
        querysets.append(
            Jednostka.objects.fulltext_filter(self.q).only("pk", "nazwa")
        )

        querysets.append(
            Autor.objects.fulltext_filter(self.q).only(
                "pk", "nazwisko", "imiona", "poprzednie_nazwiska",
                "tytul").select_related("tytul")
        )

        querysets.append(
            Zrodlo.objects.fulltext_filter(self.q).only(
                "pk", "nazwa", "poprzednia_nazwa")
        )

        querysets.append(
            Rekord.objects.fulltext_filter(self.q).only(
                "tytul_oryginalny", "content_type__model", "object_id")
        )

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class StaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class AdminNavigationAutocomplete(StaffRequired, Select2QuerySetSequenceView):
    paginate_by = 30

    def get_queryset(self):
        if not self.q:
            return []

        querysets = []

        querysets.append(
            BppUser.objects.filter(username__icontains=self.q).only(
                "pk", "username"))

        querysets.append(
            Jednostka.objects.fulltext_filter(self.q).only("pk", "nazwa")
        )

        querysets.append(
            Autor.objects.fulltext_filter(self.q).only(
                "pk", "nazwisko", "imiona", "poprzednie_nazwiska",
                "tytul").select_related("tytul")
        )

        querysets.append(
            Zrodlo.objects.fulltext_filter(self.q).only(
                "pk", "nazwa", "poprzednia_nazwa")
        )

        for klass in [Wydawnictwo_Zwarte, Wydawnictwo_Ciagle, Patent,
                      Praca_Doktorska, Praca_Habilitacyjna]:

            filter = Q(tytul_oryginalny__icontains=self.q)

            try:
                int(self.q)
                filter |= Q(pk=self.q)
            except:
                pass

            querysets.append(
                klass.objects.filter(filter).only("tytul_oryginalny")
            )

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class ZapisanyJakoAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        autor = self.forwarded.get('autor', None)

        if autor is None:
            return ['(... może najpierw wybierz autora)']

        try:
            autor_id = int(autor)
            a = Autor.objects.get(pk=autor_id)
        except (KeyError, ValueError):
            return []
        return list(
            warianty_zapisanego_nazwiska(a.imiona, a.nazwisko,
                                         a.poprzednie_nazwiska)
        )

    def get(self, request, *args, **kwargs):
        """"Return option list json response."""
        results = self.get_list()
        create_option = []
        if self.q:
            results = [x for x in results if self.q.lower() in x.lower()]
            if hasattr(self, 'create'):
                create_option = [{
                    'id': self.q,
                    'text': 'Create "%s"' % self.q,
                    'create_id': True
                }]
        return http.HttpResponse(json.dumps({
            'results': [dict(id=x, text=x) for x in results] + create_option
        }), content_type='application/json')


class PodrzednaPublikacjaHabilitacyjnaAutocomplete(
    Select2QuerySetSequenceView):
    def get_queryset(self):
        wydawnictwa_zwarte = Wydawnictwo_Zwarte.objects.all()
        wydawnictwa_ciagle = Wydawnictwo_Ciagle.objects.all()
        patenty = Patent.objects.all()

        qs = QuerySetSequence(wydawnictwa_ciagle,
                              wydawnictwa_zwarte,
                              patenty)

        autor_id = self.forwarded.get('autor', None)
        if autor_id is None:
            return qs.none()

        try:
            autor = Autor.objects.get(pk=int(autor_id))
        except (TypeError, ValueError, Autor.DoesNotExist):
            return qs.none()

        wydawnictwa_zwarte = Wydawnictwo_Zwarte.objects.filter(
            pk__in=Wydawnictwo_Zwarte_Autor.objects.filter(
                autor=autor).only('rekord')
        )
        wydawnictwa_ciagle = Wydawnictwo_Ciagle.objects.filter(
            pk__in=Wydawnictwo_Ciagle_Autor.objects.filter(
                autor=autor).only("rekord")
        )

        patenty = Patent.objects.filter(
            pk__in=Patent_Autor.objects.filter(
                autor=autor).only("rekord")
        )

        qs = QuerySetSequence(wydawnictwa_ciagle,
                              wydawnictwa_zwarte,
                              patenty)

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)

        qs = self.mixup_querysets(qs)

        return qs
