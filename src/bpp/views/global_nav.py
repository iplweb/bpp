# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseNotAllowed, HttpResponseRedirect, \
    HttpResponseBadRequest
from django.urls.base import reverse

from bpp.models.cache import Rekord

lookup_map_user = {
    "bpp.autor": (
        "bpp:browse_autor",
        lambda x: (None, {'slug': getattr(x, "slug")})
    ),
    "bpp.jednostka": (
        "bpp:browse_jednostka",
        lambda x: (None, {'slug': getattr(x, "slug")})
    ),
    "bpp.zrodlo": (
        "bpp:browse_zrodlo",
        lambda x: (None, {'slug': getattr(x, "slug")})
    ),
    "bpp.rekord": (
        "bpp:browse_praca_old",
        lambda x: (None,
                   {'model': x.content_type.model,
                    'pk': x.object_id})
    )
}


class _lookup_map_admin(dict):
    def get(self, arg):
        app_label, name = arg.split(".")
        _f = lambda x: ((x.pk,), {})
        return ('admin:%s_%s_change' % (app_label, name), _f)


lookup_map_admin = _lookup_map_admin()


def global_nav_redir(request, param):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", ])

    source = request.GET.get('source', 'user')
    if source not in ('user', 'admin'):
        return HttpResponseBadRequest()

    try:
        content_type_id, object_id = param.split("-", 1)
    except (TypeError, ValueError):
        return HttpResponseBadRequest()

    klass = ContentType.objects.get_for_id(content_type_id)
    if klass.app_label != 'bpp':
        raise NotImplementedError("Lookups for other apps not implemented")

    lookup_map = lookup_map_user
    if source == "admin":
        lookup_map = lookup_map_admin

    if klass.model == "rekord":
        object_id = [int(x.strip())
                     for x in object_id.replace("(", "")\
                         .replace(")", "")\
                         .split(",")]

    object = klass.get_object_for_this_type(pk=object_id)

    try:
        url, f = lookup_map.get("%s.%s" % (klass.app_label, klass.model))
    except (TypeError, KeyError):
        raise KeyError("dodaj wpis do mapy lookup (%s, %s)" % (source,
                                                               klass.model))
    args, kwargs = f(object)

    return HttpResponseRedirect(reverse(url, args=args, kwargs=kwargs))
