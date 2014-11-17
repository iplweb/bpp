# -*- encoding: utf-8 -*-
import re

from unidecode import unidecode


non_url = re.compile(r'[^\w-]+')

class FulltextSearchMixin:
    fts_field = 'search'

    def fulltext_filter(self, qstr):
        from djorm_pgfulltext.fields import startswith

        words = [x.strip() for x in qstr.split(u" ") if x.strip()]
        qstr = " & ".join(startswith(words))
        params = ('bpp_nazwy_wlasne', qstr)

        return self.all().extra(
            select={self.model._meta.db_table + '__rank':
                        "ts_rank_cd(" +self.model._meta.db_table + "." + self.fts_field + ", to_tsquery(%s::regconfig, %s), 16)"},
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
    if isinstance(field_or_fields, basestring):
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
        except self.klass.DoesNotExist, e:
            raise KeyError, e

    __getattr__ = __getitem__

def zrob_cache(t):
    zle_znaki = [" ", ":", ";", "-", ",", "-", ".", "(", ")", "?", "!", u"ę", u"ą", u"ł", u"ń", u"ó", u"ź", u"ż"]
    for znak in zle_znaki:
        t = t.replace(znak, "")
    return t.lower()