# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
import datetime
from django.contrib.contenttypes.models import ContentType

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.db.models.aggregates import Min
from django.http.response import HttpResponse, HttpResponseServerError
from django.utils.timezone import make_naive
from django.views.generic.base import View
from moai.oai import OAIServerFactory
from moai.server import FeedConfig

from bpp.models import Rekord, Uczelnia
from django.utils import timezone


class CacheMetadata:
    def __init__(self, orig):
        self.orig = orig

    def get(self, item, default):
        def ifhas(attr):
            if hasattr(item, attr):
                return [
                    getattr(item, attr),
                ]
            return default

        if item == "title":
            if self.orig.tytul:
                return [self.orig.tytul_oryginalny, self.orig.tytul]
            return [
                self.orig.tytul_oryginalny,
            ]

        if item == "language":
            if hasattr(self.orig, "jezyk"):
                return [
                    self.orig.jezyk.nazwa,
                ]

        if item == "creator":
            return self.orig.opis_bibliograficzny_autorzy_cache or []

        if item == "date":
            return [
                str(self.orig.rok),
            ]

        if item == "publisher":
            return ifhas("wydawnictwo")

        if item == "subject":
            return ifhas("slowa_kluczowe")

        if item == "source":
            src = []
            if getattr(self.orig, "zrodlo_id", None) is not None:
                src.append(
                    "%s %s %s"
                    % (
                        self.orig.zrodlo.nazwa,
                        self.orig.informacje,
                        self.orig.szczegoly,
                    )
                )
            else:
                if self.orig.informacje or self.orig.szczegoly:
                    src.append("%s %s" % (self.orig.informacje, self.orig.szczegoly))

            if self.orig.www:
                src.append(self.orig.www)

            return src

        if item == "type":
            return [
                self.orig.charakter_formalny.nazwa_w_primo,
            ]

        return default


def get_dc_ident(model, obj_pk):
    return "oai:bpp.umlub.pl:%s/%s" % (model, str(obj_pk))


class BPPOAIDatabase(object):
    def __init__(self, original):
        self.original = original

    def get_set(self, oai_id):
        if oai_id == 1:
            return {
                "id": "1",
                "name": "wszystkie",
                "description": "wszystkie rekordy",
                "hidden": False,
            }

        return

        row = self._sets.select(self._sets.c.set_id == oai_id).execute().fetchone()

        if row is None:
            return

    def get_setrefs(self, oai_id, include_hidden_sets=False):
        return [1]

        set_ids = []
        query = sql.select([self._setrefs.c.set_id])
        query.append_whereclause(self._setrefs.c.record_id == oai_id)
        if include_hidden_sets == False:
            query.append_whereclause(
                sql.and_(
                    self._sets.c.set_id == self._setrefs.c.set_id,
                    self._sets.c.hidden == include_hidden_sets,
                )
            )

        for row in query.execute():
            set_ids.append(row[0])
        set_ids.sort()
        return set_ids

    def record_count(self):
        return self.original.count()
        return self.original.objects.all().count()

    def set_count(self):
        return 1

    def oai_sets(self, offset=0, batch_size=20):
        yield {"id": "1", "name": "wszystkie", "description": "wszystkie rekordy"}

    def oai_earliest_datestamp(self):
        r = self.original.aggregate(Min("ostatnio_zmieniony"))
        value = r["ostatnio_zmieniony__min"]
        if value is None:
            return datetime.datetime.fromtimestamp(0)
        return value.replace(tzinfo=None)

    def oai_query(
        self,
        offset=0,
        batch_size=20,
        needed_sets=None,
        disallowed_sets=None,
        allowed_sets=None,
        from_date=None,
        until_date=None,
        identifier=None,
    ):

        needed_sets = needed_sets or []
        disallowed_sets = disallowed_sets or []
        allowed_sets = allowed_sets or []
        if batch_size < 0:
            batch_size = 0

        # make sure until date is set, and not in future
        if until_date == None or until_date > datetime.datetime.utcnow():
            until_date = timezone.now()

        query = self.original.order_by("-ostatnio_zmieniony")

        # filter dates
        query = query.filter(ostatnio_zmieniony__lte=until_date)

        if not identifier is None:
            ident = identifier.split(":")
            assert ident[0] == "oai"
            assert ident[1] == "bpp.umlub.pl"

            ident = ident[2].split("/")
            klass = ident[0].lower()

            content_type_id = ContentType.objects.get(app_label="bpp", model=klass).pk
            query = query.filter(id=[content_type_id, ident[1]])

        if not from_date is None:
            query = query.filter(ostatnio_zmieniony__gte=from_date)

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            if ukryte_statusy:
                query = query.exclude(status_korekty_id__in=ukryte_statusy)

        for row in (
            query.only(
                "ostatnio_zmieniony",
                "tytul_oryginalny",
                "tytul",
                "jezyk__nazwa",
                "rok",
                "wydawnictwo",
                "slowa_kluczowe",
                "zrodlo",
                "informacje",
                "szczegoly",
                "opis_bibliograficzny_autorzy_cache",
                "charakter_formalny__nazwa_w_primo",
                "www",
            )
            .select_related("charakter_formalny", "jezyk")
            .prefetch_related("zrodlo")[offset : offset + batch_size]
        ):
            yield {
                "id": get_dc_ident(row.content_type.model, row.object_id),
                "deleted": False,
                "modified": make_naive(
                    row.ostatnio_zmieniony, row.ostatnio_zmieniony.tzinfo
                ),
                "metadata": CacheMetadata(row),
                "sets": ["1"],
            }


class OAIView(View):
    def get(self, request, *args, **kwargs):

        base_url = request.build_absolute_uri(reverse("bpp:oai"))

        url = request.get_full_path()[len(base_url) :]

        if url.startswith("/"):
            url = url[1:]
        if url.endswith("/"):
            url = url[:-1]

        urlparts = url.split("/")

        if len(urlparts) == 0:
            return HttpResponseServerError(
                "500 Internal Server Error",
                "No server was selected, please append server name to url.",
            )

        url = "/".join(urlparts)

        db = BPPOAIDatabase(
            Rekord.objects.all().exclude(charakter_formalny__nazwa_w_primo="")
        )
        oai_server = OAIServerFactory(db, FeedConfig("bpp", base_url))
        return HttpResponse(
            content=oai_server.handleRequest(request.GET),
            content_type="application/xml",
        )
