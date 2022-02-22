import bleach
from django import shortcuts

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.http import JsonResponse
from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.defaults import page_not_found, permission_denied, server_error
from sendfile import sendfile

from bpp.models import Uczelnia


def root(request):
    """Zachowanie domyślne: przekieruj nas na pierwszą dostępną w bazie danych
    uczelnię, lub wyświetl komunikat jeżeli nie ma żadnych uczelni wpisanych do
    bazy danych."""
    # TODO: jeżeli będzie więcej, niż jeden obiekt Uczelnia...?
    uczelnia = Uczelnia.objects.only("slug").first()

    if uczelnia is None:
        return shortcuts.render(request, "browse/brak_uczelni.html")

    return shortcuts.redirect(
        reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)), permanent=True
    )


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


@csrf_exempt
def update_multiseek_title(request):
    v = request.POST.get("value")
    if not v or not len(v):
        v = ""
    from django.conf import settings

    v = bleach.clean(
        v.replace("\r\n", "\n").replace("\n", "<br/>"),
        tags=list(getattr(settings, "ALLOWED_TAGS", [])) + ["hr", "p", "br"],
    )
    request.session["MULTISEEK_TITLE"] = v
    return JsonResponse(v, safe=False)


# !/usr/bin/env python
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

TEN_YEARS = datetime.timedelta(days=3650)


def javascript_catalog(request, domain="djangojs", packages=None):
    import django.views.i18n

    response = django.views.i18n.javascript_catalog(
        request, domain=domain, packages=packages
    )
    from django.utils.translation import check_for_language

    if (
        request.GET
        and "language" in request.GET
        and check_for_language(request.GET["language"])
    ):
        expires = datetime.datetime.now() + TEN_YEARS
        response["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response["Cache-Control"] = "public"
    return response


def handler404(request, exception):
    return page_not_found(request, exception, "404.html")


def handler403(request, exception=None):
    return permission_denied(request, "403.html")


def handler500(request):
    return server_error(request, template_name="50x.html")
