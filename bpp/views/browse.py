# -*- encoding: utf-8 -*-
import json
import datetime
from django.core.handlers.wsgi import WSGIRequest

from django.core.urlresolvers import reverse
from django.db.models.aggregates import Min
from django.db.models.query_utils import Q

from django.http import Http404
from django.http.response import HttpResponse, HttpResponseServerError, \
    HttpResponseForbidden
from django.utils.timezone import make_naive
from django.views.generic import DetailView, ListView, RedirectView
from django.views.generic.base import View
from ludibrio.mock import Mock
from moai.oai import OAIServerFactory
from multiseek.logic import OR, AND
from multiseek.util import make_field
from multiseek.views import MULTISEEK_SESSION_KEY
from bpp.marc import to_marc
from bpp.models import Uczelnia, Jednostka, Wydzial, Autor, Zrodlo, Rekord, \
    Praca_Doktorska, Praca_Habilitacyjna
from bpp.multiseek_registry import JednostkaQueryObject, RokQueryObject, \
    NazwiskoIImieQueryObject, TypRekorduObject, ZrodloQueryObject


PUBLIKACJE = 'publikacje'
STRESZCZENIA = 'streszczenia'
INNE = 'inne'
TYPY = [PUBLIKACJE, STRESZCZENIA, INNE]


class UczelniaView(DetailView):
    model = Uczelnia
    template_name = "browse/uczelnia.html"


class WydzialView(DetailView):
    template_name = "browse/wydzial.html"
    model = Wydzial


class JednostkaView(DetailView):
    template_name = "browse/jednostka.html"
    model = Jednostka

    def get_context_data(self, **kwargs):
        return super(JednostkaView, self).get_context_data(
            typy=TYPY, **kwargs)


class AutorView(DetailView):
    template_name = "browse/autor.html"
    model = Autor

    def get_context_data(self, **kwargs):
        return super(AutorView, self).get_context_data(
            typy=TYPY, **kwargs)


LITERKI = u'ABCDEFGHIJKLMNOPQRSTUVWYXZ'

PODWOJNE = {
    'A': ['A', 'Ą'],
    'C': ['C', 'Ć'],
    'E': ['E', 'Ę'],
    'L': ['L', 'Ł'],
    'N': ['N', 'Ń'],
    'O': ['O', 'Ó'],
    'Z': ['Z', 'Ź', 'Ż']
}


class Browser(ListView):
    model = None
    param = None
    literka_field = None

    def get_search_string(self):
        return self.request.GET.get(self.param)

    def get_literka(self):
        return self.kwargs.get('literka')

    def get_queryset(self):
        literka = self.get_literka()
        sstr = self.get_search_string()

        if sstr:
            qry = self.model.objects.fulltext_filter(self.get_search_string())
        else:
            qry = self.model.objects.all()

        if literka:
            args = [literka]
            if literka in PODWOJNE:
                args = PODWOJNE[literka]

            qobj = Q(**{self.literka_field + "__istartswith": literka})
            for l in args[1:]:
                qobj |= Q(**{self.literka_field + "__istartswith": l})
            qry = qry.filter(qobj)  # **{self.param + "__istartswith": literka})

        return qry.distinct()

    def get_context_data(self, *args, **kw):
        return super(Browser, self).get_context_data(
            flt=self.request.GET.get(self.param),
            literki=LITERKI,
            wybrana=self.kwargs.pop('literka', None),
            *args, **kw)


class AutorzyView(Browser):
    template_name = "browse/autorzy.html"
    model = Autor
    param = 'search'
    literka_field = 'nazwisko'


class ZrodlaView(Browser):
    template_name = "browse/zrodla.html"
    model = Zrodlo
    param = 'search'
    literka_field = 'nazwa'


class JednostkiView(Browser):
    template_name = "browse/jednostki.html"
    model = Jednostka
    param = 'search'
    literka_field = 'nazwa'

    def get_queryset(self):
        qry = super(JednostkiView, self).get_queryset()
        return qry.filter(widoczna=True)


class ZrodloView(DetailView):
    model = Zrodlo
    template_name = 'browse/zrodlo.html'


def zrob_box(values, name, qo):
    ret = []
    po = None
    for value in values:
        ret.append(make_field(qo, qo.ops[0], value, prev_op=po))
        po = OR
    return ret


def zrob_box_z_requestu(dct, name, qo):
    if dct.get(name):
        return zrob_box(dct.getlist(name), name, qo)
    return []


def zrob_formularz(*args):
    ret = [None]

    prev_op = None

    for arg in [x for x in args if x]:

        if len(arg) > 1:
            lst = [prev_op]
            lst.extend(arg)
            ret.append(lst)
        else:
            arg[0]['prev_op'] = prev_op
            ret.append(arg[0])

        prev_op = AND

    return json.dumps({'form_data': ret})


class BuildSearch(RedirectView):
    def get_redirect_url(self, **kwargs):
        return reverse("multiseek:index")

    def post(self, *args, **kw):
        zrodla_box = zrob_box_z_requestu(self.request.POST, 'zrodlo',
                                         ZrodloQueryObject)
        typy_box = zrob_box_z_requestu(self.request.POST, 'typ',
                                       TypRekorduObject)
        lata_box = zrob_box_z_requestu(self.request.POST, 'rok', RokQueryObject)
        jednostki_box = zrob_box_z_requestu(self.request.POST, 'jednostka',
                                            JednostkaQueryObject)
        autorzy_box = zrob_box_z_requestu(self.request.POST, 'autor',
                                          NazwiskoIImieQueryObject)

        self.request.session[MULTISEEK_SESSION_KEY] = zrob_formularz(
            zrodla_box, autorzy_box, typy_box, jednostki_box, lata_box)

        self.request.session["MULTISEEK_TITLE"] = self.request.POST.get(
            'suggested-title', '')

        return super(BuildSearch, self).post(*args, **kw)


class PracaView(DetailView):
    template_name = "browse/praca.html"
    model = Rekord

    def get_object(self, queryset=None):
        try:
            obj = Rekord.objects.get(
                content_type__app_label='bpp',
                content_type__model=self.kwargs['model'],
                object_id=self.kwargs['pk'])
        except Rekord.DoesNotExist:
            raise Http404

        return obj