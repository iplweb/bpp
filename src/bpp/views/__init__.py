import datetime
from pathlib import Path

import nh3
from django import shortcuts
from django.conf import settings

try:
    pass
except ImportError:
    pass

from django.http import JsonResponse
from django.http.response import HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.defaults import page_not_found, permission_denied
from django_sendfile import sendfile

from bpp.models import Uczelnia


def root(request):
    """Wyświetl stronę główną z pierwszą dostępną w bazie danych
    uczelnią, lub wyświetl komunikat jeżeli nie ma żadnych uczelni wpisanych do
    bazy danych."""
    # TODO: jeżeli będzie więcej, niż jeden obiekt Uczelnia...?
    uczelnia = Uczelnia.objects.first()

    if uczelnia is None:
        return shortcuts.render(request, "browse/brak_uczelni.html")

    # Użyj wspólnej funkcji z browse.py aby uniknąć duplikacji kodu
    from bpp.views.browse import get_uczelnia_context_data

    context = get_uczelnia_context_data(uczelnia)
    context["show_zglos_button"] = uczelnia.sprawdz_uprawnienie(
        "formularz_zglaszania_publikacji", request
    )

    return shortcuts.render(request, "browse/uczelnia.html", context)


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

    v = nh3.clean(
        v.replace("\r\n", "\n").replace("\n", "<br/>"),
        tags=set(getattr(settings, "ALLOWED_TAGS", [])) | {"hr", "p", "br"},
        clean_content_tags=set(),
        link_rel=None,
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
    return permission_denied(request, exception, "403.html")


def handler500(request):
    # Serwuje pre-renderowany 500.html z STATIC_ROOT (generuje go
    # `generate_500_page` w fazie 2 entrypointu kontenera).
    # Renderowanie 50x.html w runtime było rekurencyjne: Django stdlib
    # `server_error()` woła `template.render()` bez request, więc context
    # processory nie odpalają, `THEME_NAME` jest pusty, kompresor próbuje
    # otworzyć STATIC_ROOT jako plik → IsADirectoryError.
    static_500 = Path(settings.STATIC_ROOT) / "500.html"
    try:
        body = static_500.read_text(encoding="utf-8")
    except OSError:
        body = (
            "<!doctype html><html lang='pl'><meta charset='utf-8'>"
            "<title>Błąd 500</title>"
            "<h1>Wystąpił błąd serwera</h1>"
            "<p>Spróbuj ponownie za chwilę.</p>"
        )
    return HttpResponseServerError(body, content_type="text/html; charset=utf-8")


def _read_static_robots(settings):
    """Zwróć treść statycznego robots.txt (lista Disallow).

    Najpierw STATIC_ROOT (produkcja po collectstatic), w razie braku —
    przez staticfiles finders (dev/test, gdzie collectstatic nie biegł).
    """
    import os

    candidate = os.path.join(settings.STATIC_ROOT or "", "robots.txt")
    if os.path.exists(candidate):
        path = candidate
    else:
        from django.contrib.staticfiles import finders

        path = finders.find("robots.txt")

    if not path:
        # Nie powinno się zdarzyć — robots.txt jest w src/bpp/static/.
        return "User-agent: *\n"

    with open(path, encoding="utf-8") as f:
        return f.read()


def robots_txt(request):
    """Serwuj robots.txt z host-zależną dyrektywą Sitemap.

    W konfiguracji testowej blokujemy całość (Disallow: /) i nie ogłaszamy
    sitemapy. W produkcji do listy Disallow dopisujemy bezwzględny URL
    sitemapy zbudowany z hosta requestu — poprawny dla każdego z domen
    multi-hosted (hardcode jednej domeny byłby błędny dla pozostałych).
    """
    from django.conf import settings

    if getattr(settings, "DJANGO_BPP_ENABLE_TEST_CONFIGURATION", False):
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")

    body = _read_static_robots(settings).rstrip("\n")
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    body = f"{body}\n\nSitemap: {sitemap_url}\n"
    return HttpResponse(body, content_type="text/plain")
