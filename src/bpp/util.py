# -*- encoding: utf-8 -*-
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from django.apps import apps
from psycopg2.extensions import QuotedString
from unidecode import unidecode

non_url = re.compile(r'[^\w-]+')


def get_fixture(name):
    p = Path(__file__).parent / "fixtures" / ("%s.json" % name)
    ret = json.load(open(p, 'rb'))
    ret = [x['fields'] for x in ret if x['model'] == ("bpp.%s" % name)]
    return dict([(x['skrot'].lower().strip(), x) for x in ret])


def fulltext_tokenize(s):
    s = s.replace(":", "") \
        .replace('*', "") \
        .replace('"', "") \
        .replace('|', " ") \
        .replace("'", "") \
        .replace("&", "") \
        .replace("\\", "") \
        .replace("(", "") \
        .replace(")", "") \
        .replace("\t", " ") \
        .replace("\n", " ") \
        .replace("\r", " ")
    return [x.strip() for x in s.split(" ") if x.strip()]


class FulltextSearchMixin:
    fts_field = 'search'

    def fulltext_filter(self, qstr):
        def quotes(wordlist):
            ret = []
            for elem in wordlist:
                ret.append(
                    str(
                        QuotedString(
                            elem.replace("\\", "").encode("utf-8")
                        )
                    )
                )
            return ret

        def startswith(wordlist):
            return [x + ":*" for x in quotes(wordlist)]

        def negative(wordlist):
            return ['!' + x for x in startswith(wordlist)]

        if qstr == None:
            qstr = ""

        if type(qstr) == bytes:
            qstr = qstr.decode("utf-8")

        words = fulltext_tokenize(qstr)
        qstr = " & ".join(startswith(words))
        params = ('bpp_nazwy_wlasne', qstr)

        return self.all().extra(
            select={self.model._meta.db_table + '__rank':
                        "ts_rank_cd(" + self.model._meta.db_table + "." + self.fts_field + ", to_tsquery(%s::regconfig, %s), 16)"},
            select_params=params,
            where=[self.model._meta.db_table + "." + self.fts_field + " @@ to_tsquery(%s::regconfig, %s)"],
            params=params,
            order_by=['-' + self.model._meta.db_table + '__rank'])


def slugify_function(s):
    s = unidecode(s).replace(" ", "-")
    return non_url.sub('', s)


def get_original_object(object_name, object_pk):
    from bpp.models import TABLE_TO_MODEL
    klass = TABLE_TO_MODEL.get(object_name)
    try:
        return klass.objects.get(pk=object_pk)
    except klass.DoesNotExist:
        return


def get_copy_from_db(instance):
    if not instance.pk:
        return None
    return instance.__class__._default_manager.get(pk=instance.pk)


def has_changed(instance, field_or_fields):
    try:
        original = get_copy_from_db(instance)
    except instance.__class__.DoesNotExist:
        return True
        # Jeżeli w bazie danych nie ma tego obiektu, no to bankowo
        # się zmienił...
        return True

    fields = field_or_fields
    if isinstance(field_or_fields, str):
        fields = [field_or_fields]

    for field in fields:
        if not getattr(instance, field) == getattr(original, field):
            return True

    return False


class Getter:
    """Klasa pomocnicza dla takich danych jak Typ_KBN czy
    Charakter_Formalny, umozliwia po zainicjowaniu pobieranie
    tych klas po atrybucie w taki sposob:

    >>> kbn = Getter(Typ_KBN)
    >>> kbn.PO == Typ_KBN.objects.get(skrot='PO')
    True
    """

    def __init__(self, klass, field='skrot'):
        self.field = field
        self.klass = klass

    def __getitem__(self, item):
        kw = {self.field: item}
        return self.klass.objects.get(**kw)

    __getattr__ = __getitem__


class NewGetter(Getter):
    """Zwraca KeyError zamiast DoesNotExist."""

    def __getitem__(self, item):
        kw = {self.field: item}
        try:
            return self.klass.objects.get(**kw)
        except self.klass.DoesNotExist as e:
            raise KeyError(e)

    __getattr__ = __getitem__


def zrob_cache(t):
    zle_znaki = [" ", ":", ";", "-", ",", "-", ".", "(", ")", "?", "!", "ę", "ą", "ł", "ń", "ó", "ź", "ż"]
    for znak in zle_znaki:
        t = t.replace(znak, "")
    return t.lower()


def remove_old_objects(klass, file_field="file", field_name="created_on", days=7):
    since = datetime.now() - timedelta(days=days)

    kwargs = {}
    kwargs["%s__lt" % field_name] = since

    for rec in klass.objects.filter(**kwargs):
        try:
            path = getattr(rec, file_field).path
        except ValueError:
            path = None

        rec.delete()

        if path is not None:
            try:
                os.unlink(path)
            except OSError:
                pass


def rebuild_contenttypes():
    app_config = apps.get_app_config('bpp')
    from django.contrib.contenttypes.management import create_contenttypes
    create_contenttypes(app_config, verbosity=0)
