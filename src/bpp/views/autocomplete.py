# -*- encoding: utf-8 -*-

import json

from dal import autocomplete
from django import http
from django.db.models.query_utils import Q
from django.template.defaultfilters import safe
from django.urls.base import reverse
from django.utils.text import Truncator

from bpp.lookups import SearchQueryStartsWith
from bpp.models import Jednostka
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.zrodlo import Zrodlo


class JednostkaAutocomplete(autocomplete.Select2QuerySetView):
    qset = Jednostka.objects.all()

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


class UserNavigationAutocomplete(autocomplete.Select2ListView):
    def get_result_label(self, model, name):
        return '<img width="16" height="16" src="/static/bpp/svg/%s.svg"> ' \
               '%s' % (
                   model, safe(Truncator(name).chars(200)))

    def get(self, request, *args, **kwargs):
        return http.HttpResponse(json.dumps({
            'results': self.get_results()
        }))

    def get_results(self):
        elements = []
        q = self.q

        def doloz(model, qset, url, label=lambda x: unicode(x), attr='slug'):
            no_obj = 0

            for obj in qset:
                elements.append(dict(
                    text=self.get_result_label(
                        model=model._meta.object_name.lower(),
                        name=label(obj)),
                    id=reverse(url, args=(getattr(obj, attr),))
                ))

        def doloz_rekord(qset):
            for obj in qset:
                elements.append(dict(
                    text=self.get_result_label(
                        model=obj.content_type.model,
                        name=obj.tytul_oryginalny),
                    id=reverse(
                        "bpp:browse_praca",
                        args=(obj.content_type.model, obj.object_id))
                ))

        doloz(
            Jednostka,
            Jednostka.objects.fulltext_filter(q).only("pk", "nazwa")[:5],
            'bpp:browse_jednostka')

        doloz(Autor,
              Autor.objects.fulltext_filter(q).only("pk", "nazwisko", "imiona",
                                                    "poprzednie_nazwiska",
                                                    "tytul").select_related()[
              :5],
              'bpp:browse_autor')

        doloz(Zrodlo,
              Zrodlo.objects.fulltext_filter(q).only("pk", "nazwa",
                                                     "poprzednia_nazwa")[:5],
              'bpp:browse_zrodlo')

        doloz_rekord(Rekord.objects.fulltext_filter(q).only("tytul_oryginalny",
                                                            "content_type__model",
                                                            "object_id")[:6])

        try:
            look_for_pk = int(q)
            doloz_rekord(Rekord.objects.filter(object_id=look_for_pk))
        except:
            pass

        # DSU
        elements = [(x['text'], x) for x in elements]
        elements.sort()
        elements = [x[1] for x in elements]

        return elements
