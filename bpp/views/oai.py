# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
import datetime
from django.contrib.contenttypes.models import ContentType

from django.core.urlresolvers import reverse
from django.db.models.aggregates import Min
from django.http.response import HttpResponse, HttpResponseServerError
from django.utils.timezone import make_naive
from django.views.generic.base import View
from moai.oai import OAIServerFactory
from moai.server import FeedConfig

from bpp.models import Rekord


class CacheMetadata:
    def __init__(self, orig):
        self.orig = orig

    def get(self, item, default):

        def ifhas(attr):
            if hasattr(item, attr):
                return [getattr(item, attr),]
            return default

        if item == 'title':
            return [self.orig.tytul_oryginalny,]
        if item == 'language':
            if hasattr(self.orig, 'jezyk'):
                return [self.orig.jezyk.nazwa,]
        if item == 'creator':
            return self.orig.opis_bibliograficzny_autorzy_cache or []

        if item == "date":
            return [str(self.orig.rok),]

        if item == 'publisher':
            return ifhas('wydawnictwo')

        if item == "subject":
            return ifhas("slowa_kluczowe")

        if item == "source":
            if self.orig.zrodlo:
                return ["%s %s %s" % (self.orig.zrodlo.nazwa, self.orig.informacje, self.orig.szczegoly)]
            else:
                if self.orig.informacje or self.orig.szczegoly:
                    return ["%s %s" % (self.orig.informacje, self.orig.szczegoly)]

        return default


def get_dc_ident(model, obj_pk):
    return "oai:bpp.umlub.pl:%s/%s" % (model, str(obj_pk))

class BPPOAIDatabase(object):
    def __init__(self, original):
        self.original = original

        #self._db = self._connect()
        #self._records = self._db.tables['records']
        #self._sets = self._db.tables['sets']
        #self._setrefs = self._db.tables['setrefs']
        #self._reset_cache()

    # def _connect(self):
    #     dburi = self._uri
    #     if dburi is None:
    #         dburi = 'sqlite:///:memory:'
    #
    #     engine = sql.create_engine(dburi)
    #     db = sql.MetaData(engine)
    #
    #     sql.Table('records', db,
    #               sql.Column('record_id', sql.Unicode, primary_key=True),
    #               sql.Column('modified', sql.DateTime, index=True),
    #               sql.Column('deleted', sql.Boolean),
    #               sql.Column('metadata', sql.String))
    #
    #     sql.Table('sets', db,
    #               sql.Column('set_id', sql.Unicode, primary_key=True),
    #               sql.Column('hidden', sql.Boolean),
    #               sql.Column('name', sql.Unicode),
    #               sql.Column('description', sql.Unicode))
    #
    #     sql.Table('setrefs', db,
    #               sql.Column('record_id', sql.Integer,
    #                          sql.ForeignKey('records.record_id'),
    #                          index=True, primary_key=True),
    #               sql.Column('set_id', sql.Integer,
    #                          sql.ForeignKey('sets.set_id'),
    #                          index=True, primary_key=True))
    #
    #     db.create_all()
    #     return db

    # def flush(self):
    #     oai_ids = set()
    #     for row in sql.select([self._records.c.record_id]).execute():
    #         oai_ids.add(row[0])
    #     for row in sql.select([self._sets.c.set_id]).execute():
    #         oai_ids.add(row[0])
    #
    #     deleted_records = []
    #     deleted_sets = []
    #     deleted_setrefs = []
    #
    #     inserted_records = []
    #     inserted_sets = []
    #     inserted_setrefs = []
    #
    #
    #     for oai_id, item in self._cache['records'].items():
    #         if oai_id in oai_ids:
    #             # record allready exists
    #             deleted_records.append(oai_id)
    #         item['record_id'] = oai_id
    #         inserted_records.append(item)
    #
    #     for oai_id, item in self._cache['sets'].items():
    #         if oai_id in oai_ids:
    #             # set allready exists
    #             deleted_sets.append(oai_id)
    #         item['set_id'] = oai_id
    #         inserted_sets.append(item)
    #
    #     for record_id, set_ids in self._cache['setrefs'].items():
    #         deleted_setrefs.append(record_id)
    #         for set_id in set_ids:
    #             inserted_setrefs.append(
    #                 {'record_id':record_id, 'set_id': set_id})
    #
    #     # delete all processed records before inserting
    #     if deleted_records:
    #         self._records.delete(
    #             self._records.c.record_id == sql.bindparam('record_id')
    #             ).execute(
    #             [{'record_id': rid} for rid in deleted_records])
    #     if deleted_sets:
    #         self._sets.delete(
    #             self._sets.c.set_id == sql.bindparam('set_id')
    #             ).execute(
    #             [{'set_id': sid} for sid in deleted_sets])
    #     if deleted_setrefs:
    #         self._setrefs.delete(
    #             self._setrefs.c.record_id == sql.bindparam('record_id')
    #             ).execute(
    #             [{'record_id': rid} for rid in deleted_setrefs])
    #
    #     # batch inserts
    #     if inserted_records:
    #         self._records.insert().execute(inserted_records)
    #     if inserted_sets:
    #         self._sets.insert().execute(inserted_sets)
    #     if inserted_setrefs:
    #         self._setrefs.insert().execute(inserted_setrefs)
    #
    #     self._reset_cache()
    #
    # def _reset_cache(self):
    #     self._cache = {'records': {}, 'sets': {}, 'setrefs': {}}
    #
    #
    # def update_record(self, oai_id, modified, deleted, sets, metadata):
    #     # adds a record, call flush to actually store in db
    #
    #     check_type(oai_id,
    #                unicode,
    #                prefix="record %s" % oai_id,
    #                suffix='for parameter "oai_id"')
    #     check_type(modified,
    #                datetime.datetime,
    #                prefix="record %s" % oai_id,
    #                suffix='for parameter "modified"')
    #     check_type(deleted,
    #                bool,
    #                prefix="record %s" % oai_id,
    #                suffix='for parameter "deleted"')
    #     check_type(sets,
    #                dict,
    #                unicode_values=True,
    #                recursive=True,
    #                prefix="record %s" % oai_id,
    #                suffix='for parameter "sets"')
    #     check_type(metadata,
    #                dict,
    #                prefix="record %s" % oai_id,
    #                suffix='for parameter "metadata"')
    #
    #     def date_handler(obj):
    #         if hasattr(obj, 'isoformat'):
    #             return obj.isoformat()
    #         else:
    #             raise TypeError, 'Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj))
    #
    #     metadata = json.dumps(metadata, default=date_handler)
    #     self._cache['records'][oai_id] = (dict(modified=modified,
    #                                            deleted=deleted,
    #                                            metadata=metadata))
    #     self._cache['setrefs'][oai_id] = []
    #     for set_id in sets:
    #         self._cache['sets'][set_id] = dict(
    #             name = sets[set_id]['name'],
    #             description = sets[set_id].get('description'),
    #             hidden = sets[set_id].get('hidden', False))
    #         self._cache['setrefs'][oai_id].append(set_id)

    # def get_record(self, oai_id):
    #     row = self._records.select(
    #         self._records.c.record_id == oai_id).execute().fetchone()
    #     if row is None:
    #         return
    #
    #     record = {'id': row.record_id,
    #               'deleted': row.deleted,
    #               'modified': row.modified,
    #               'metadata': json.loads(row.metadata),
    #               'sets': [1]} # self.get_setrefs(oai_id)}
    #     return record

    def get_set(self, oai_id):
        if oai_id == 1:
            return {'id': "1",
                    'name': "wszystkie",
                    'description': "wszystkie rekordy",
                    'hidden': False}

        return

        row = self._sets.select(
            self._sets.c.set_id == oai_id).execute().fetchone()
        if row is None:
            return
        # return {'id': row.set_id,
        #         'name': row.name,
        #         'description': row.description,
        #         'hidden': row.hidden}

    def get_setrefs(self, oai_id, include_hidden_sets=False):
        return [1]

        set_ids = []
        query = sql.select([self._setrefs.c.set_id])
        query.append_whereclause(self._setrefs.c.record_id == oai_id)
        if include_hidden_sets == False:
            query.append_whereclause(
                sql.and_(self._sets.c.set_id == self._setrefs.c.set_id,
                         self._sets.c.hidden == include_hidden_sets))

        for row in query.execute():
            set_ids.append(row[0])
        set_ids.sort()
        return set_ids

    def record_count(self):
        return self.original.count()
        return self.original.objects.all().count()

    def set_count(self):
        return 1

    # def remove_record(self, oai_id):
    #     self._records.delete(
    #         self._records.c.record_id == oai_id).execute()
    #     self._setrefs.delete(
    #         self._setrefs.c.record_id == oai_id).execute()
    #
    # def remove_set(self, oai_id):
    #     self._sets.delete(
    #         self._sets.c.set_id == oai_id).execute()
    #     self._setrefs.delete(
    #         self._setrefs.c.set_id == oai_id).execute()
    #
    def oai_sets(self, offset=0, batch_size=20):
        yield {'id': "1",
               'name': "wszystkie",
               'description': "wszystkie rekordy"}

    def oai_earliest_datestamp(self):
        r = self.original.aggregate(Min('ostatnio_zmieniony'))
        value = r['ostatnio_zmieniony__min']
        if value is None:
            return datetime.fromtimestamp(0)
        return value.replace(tzinfo=None)


    def oai_query(self,
                  offset=0,
                  batch_size=20,
                  needed_sets=None,
                  disallowed_sets=None,
                  allowed_sets=None,
                  from_date=None,
                  until_date=None,
                  identifier=None):

        needed_sets = needed_sets or []
        disallowed_sets = disallowed_sets or []
        allowed_sets = allowed_sets or []
        if batch_size < 0:
            batch_size = 0

        # make sure until date is set, and not in future
        if until_date == None or until_date > datetime.datetime.utcnow():
            until_date = datetime.datetime.now()

        query = self.original.order_by('-ostatnio_zmieniony')

        # filter dates
        query = query.filter(ostatnio_zmieniony__lte=until_date)

        if not identifier is None:
            ident = identifier.split(":")
            assert(ident[0] == "oai")
            assert(ident[1] == "bpp.umlub.pl")

            ident = ident[2].split("/")
            klass = ident[0].lower()

            content_type_id = ContentType.objects.get(app_label='bpp', model=klass).pk
            query = query.filter(content_type_id=content_type_id, object_id=ident[1])

        if not from_date is None:
            query = query.filter(ostatnio_zmieniony__gte=from_date)

        print from_date, until_date



        # filter sets
        #
        # setclauses = []
        # for set_id in needed_sets:
        #     alias = self._setrefs.alias()
        #     setclauses.append(
        #         sql.and_(
        #         alias.c.set_id == set_id,
        #         alias.c.record_id == self._records.c.record_id))
        #
        # if setclauses:
        #     query.append_whereclause((sql.and_(*setclauses)))

        # allowed_setclauses = []
        # for set_id in allowed_sets:
        #     alias = self._setrefs.alias()
        #     allowed_setclauses.append(
        #         sql.and_(
        #         alias.c.set_id == set_id,
        #         alias.c.record_id == self._records.c.record_id))
        #
        # if allowed_setclauses:
        #     query.append_whereclause(sql.or_(*allowed_setclauses))
        #
        # disallowed_setclauses = []
        # for set_id in disallowed_sets:
        #     alias = self._setrefs.alias()
        #     disallowed_setclauses.append(
        #         sql.exists([self._records.c.record_id],
        #                    sql.and_(
        #         alias.c.set_id == set_id,
        #         alias.c.record_id == self._records.c.record_id)))
        #
        # if disallowed_setclauses:
        #     query.append_whereclause(sql.not_(sql.or_(*disallowed_setclauses)))
        #

        for row in query.only(
            "ostatnio_zmieniony", "object_id", "content_type__model", "tytul_oryginalny",
            "tytul_oryginalny", "jezyk__nazwa", "rok", "wydawnictwo",
            "slowa_kluczowe", "zrodlo", "informacje", "szczegoly",
            "opis_bibliograficzny_autorzy_cache"
        ).select_related()[offset:offset+batch_size]:
            yield {'id': get_dc_ident(row.content_type.model, row.object_id),
                   'deleted': False,
                   'modified': make_naive(row.ostatnio_zmieniony, row.ostatnio_zmieniony.tzinfo),
                   'metadata': CacheMetadata(row),
                   'sets': ['1']}


class OAIView(View):
    def get(self, request, *args, **kwargs):

        base_url = request.build_absolute_uri(reverse("bpp:oai"))

        url = request.get_full_path()[len(base_url):]

        if url.startswith('/'):
            url = url[1:]
        if url.endswith('/'):
            url = url[:-1]

        urlparts = url.split('/')

        if len(urlparts) == 0:
            return HttpResponseServerError('500 Internal Server Error',
                 'No server was selected, please append server name to url.')

        url = '/'.join(urlparts)

        # if self.is_asset_url(url, self._config):
        #     if self.allow_download(url, self._config):
        #         # return self.download_asset(req, url, self._config)
        #         raise NotImplementedError
        #     else:
        #         return HttpResponseForbidden(
        #             '403 Forbidden',
        #             'You are not allowed to download this asset')

        db = BPPOAIDatabase(Rekord.objects.all()) # filter(search__ft_startswith=['test']))
        oai_server = OAIServerFactory(db, FeedConfig(
            "bpp", base_url)) # , metadata_prefixes=['oai_dc','marc']))
        return HttpResponse(content=oai_server.handleRequest(request.GET))
