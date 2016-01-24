# -*- encoding: utf-8 -*-

from django import shortcuts
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from sendfile import sendfile

from bpp.models.cache import Rekord
from bpp.views.utils import JSONResponseMixin
from bpp.models import Autor, Jednostka, Zrodlo, \
    Uczelnia


def zapytaj_o_autora(q):
    myQ = Q()
    for elem in q.split(" "):
        myQ = myQ & Q(
            Q(nazwisko__istartswith=elem) |
            Q(imiona__istartswith=elem) |
            Q(poprzednie_nazwiska__istartswith=elem))
    return myQ


def navigation_autocomplete(
        request, template_name='navigation_autocomplete.html'):
    q = request.GET.get('q', '')
    context = {'q': q}

    # % url admin:bpp_wydawnictwo_zwarte_change wydawnictwo.pk %}

    # element.model
    # element.label
    # element.url

    #{% for wydawnictwo in wydawnictwa_zwarte %}
    #{% for wydawnictwo in wydawnictwa_ciagle %}
    #{% for patent in patenty %}
    #{% for praca in prace_doktorskie %}
    #{% for praca in prace_habilitacyjne %}
    #{% for jednostka in jednostki %}
    #{% for autor in autorzy %}
    #{% for user in users %}

    elements = []
    user = request.user

    def doloz(model, qset, label=lambda x: unicode(x)):

        for obj in qset:

            if model == Rekord:
                app_label = 'bpp'
                object_name = obj.content_type.model
                object_pk = obj.object_id
            else:
                app_label = obj._meta.app_label
                object_name = obj._meta.object_name.lower()
                object_pk = obj.pk

            url = 'admin:%s_%s_change' % (app_label, object_name)

            elements.append(dict(
                model=object_name,
                label=label(obj),
                url=reverse(url, args=(object_pk, ))
            ))

    if user.is_staff or user.groups.filter(name="administracja"):
        User = get_user_model()

        qset = User.objects.filter(
            Q(username__istartswith=q) |
            Q(first_name__istartswith=q) |
            Q(last_name__istartswith=q) |
            Q(email__istartswith=q)
        ).distinct()[:6]

        doloz(User, qset)

    if user.is_staff or user.groups.filter(name="struktura"):
        doloz(Jednostka, Jednostka.objects.fulltext_filter(q)[:6])

    if user.is_staff or user.groups.filter(name="indeks_autorow") or \
            user.groups.filter(name="wprowadzanie danych"):

        doloz(Autor, Autor.objects.fulltext_filter(q)[:6])
        doloz(Zrodlo, Zrodlo.objects.fulltext_filter(q)[:6])
        doloz(Rekord, Rekord.objects.fulltext_filter(q).only(
            "tytul_oryginalny", "content_type_id", "object_id").select_related()[:6])

    try:
        look_for_pk = int(q)
        recs = Rekord.objects.filter(object_id=look_for_pk).only("tytul_oryginalny", "content_type_id", "object_id")
        doloz(Rekord, recs)
    except:
        pass

    # DSU
    elements = [(x['label'], x) for x in elements]
    elements.sort()
    elements = [x[1] for x in elements]

    context['elements'] = elements

    return shortcuts.render(request, template_name, context)


def user_navigation_autocomplete(
        request, template_name='user_navigation_autocomplete.html'):
    elements = []
    q = request.GET.get('q', '')
    context = {'q': q}

    def doloz(model, qset, url, label=lambda x: unicode(x), attr='slug'):
        no_obj = 0

        for obj in qset:
            elements.append(dict(
                model=model._meta.object_name.lower(),
                label=label(obj),
                url=reverse(url, args=(getattr(obj, attr), ))
            ))

    def doloz_rekord(qset):
        for obj in qset:
            elements.append(dict(
                model=obj.content_type.model,
                label=obj.tytul_oryginalny,
                url=reverse(
                    "bpp:browse_praca",
                    args=(obj.content_type.model, obj.object_id))
            ))

    doloz(
        Jednostka, Jednostka.objects.fulltext_filter(q).only("pk", "nazwa")[:5],
        'bpp:browse_jednostka')

    doloz(Autor, Autor.objects.fulltext_filter(q).only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul").select_related()[:5],
          'bpp:browse_autor')

    doloz(Zrodlo,
          Zrodlo.objects.fulltext_filter(q).only("pk", "nazwa", "poprzednia_nazwa")[:5],
          'bpp:browse_zrodlo')

    doloz_rekord(Rekord.objects.fulltext_filter(q).only("tytul_oryginalny", "content_type__model", "object_id")[:6])

    try:
        look_for_pk = int(q)
        doloz_rekord(Rekord.objects.filter(object_id=look_for_pk))
    except:
        pass

    # DSU
    elements = [(x['label'], x) for x in elements]
    elements.sort()
    elements = [x[1] for x in elements]

    context['elements'] = elements

    return shortcuts.render(request, template_name, context)


def autorform_dependant_js(request):
    return shortcuts.render(request, "autorform_dependant.js", {
        'class': request.GET.get('class', 'NO CLASS ON REQUEST').lower()
    }, content_type='text/javascript')


def root(request):
    """Zachowanie domyślne: przekieruj nas na pierwszą dostępną w bazie danych
    uczelnię, lub wyświetl komunikat jeżeli nie ma żadnych uczelni wpisanych do
    bazy danych."""
    try:
        # TODO: jeżeli będzie więcej, niż jeden obiekt Uczelnia, to co?
        uczelnia = Uczelnia.objects.all()[0]
    except IndexError:
        return shortcuts.render(request, "browse/brak_uczelni.html")

    return shortcuts.redirect(
        reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))


def favicon(request):
    try:
        fn = Uczelnia.objects.get(pk=1).favicon_ico
    except Uczelnia.DoesNotExist:
        return HttpResponse("create Uczelnia object first")

    try:
        return sendfile(request, fn.path)
    except ValueError:
        return HttpResponse("icon image is not set")
        # raise Http404


from .mymultiseek import *


@csrf_exempt
def update_multiseek_title(request):
    v = request.POST.get('value')
    if not v or not len(v):
        v = ''
    request.session["MULTISEEK_TITLE"] = v
    return HttpResponse(v)


#!/usr/bin/env python
# vim:ts=4:sw=4:et:ft=python
#
# Caching decorator for Django /jsi18n/
# http://wtanaka.com/django/jsi18ncache
#
# Copyright (C) 2009 Wesley Tanaka <http://wtanaka.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
TEN_YEARS=datetime.timedelta(days=3650)

def javascript_catalog(request, domain='djangojs', packages=None):
    import django.views.i18n
    response = django.views.i18n.javascript_catalog(request,
            domain=domain,
            packages=packages)
    from django.utils.translation import check_for_language
    if request.GET and \
            request.GET.has_key('language') and \
            check_for_language(request.GET['language']):
        expires = datetime.datetime.now() + TEN_YEARS
        response['Expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S GMT')
        response['Cache-Control'] = 'public'
    return response