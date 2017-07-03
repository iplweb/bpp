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
            'language' in request.GET and \
            check_for_language(request.GET['language']):
        expires = datetime.datetime.now() + TEN_YEARS
        response['Expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S GMT')
        response['Cache-Control'] = 'public'
    return response