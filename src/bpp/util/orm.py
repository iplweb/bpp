import operator
import os
from datetime import timedelta
from functools import reduce

from django.apps import apps
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Value
from django.utils import timezone

from bpp.util.text import fulltext_tokenize


class FulltextSearchMixin:
    fts_field = "search"

    # włączaj typ wyszukoiwania web-search gdy podany jest znak minus
    # w tekscie zapytania:
    fts_enable_websearch_on_minus_or_quote = True

    def fulltext_empty(self):
        return self.none().annotate(**{self.fts_field + "__rank": Value(0)})

    def fulltext_annotate(self, search_query, normalization):
        return {
            self.fts_field + "__rank": SearchRank(
                self.fts_field, search_query, normalization=normalization
            )
        }

    def fulltext_filter(self, qstr, normalization=None):
        if qstr is None:
            return self.fulltext_empty()

        if isinstance(qstr, bytes):
            qstr = qstr.decode("utf-8")

        # Remove " - " (space-dash-space) from the query string
        qstr = qstr.replace(" - ", " ")

        words = fulltext_tokenize(qstr)
        if not words:
            return self.fulltext_empty()

        if (
            qstr.find("-") >= 0 or qstr.find('"') >= 0
        ) and self.fts_enable_websearch_on_minus_or_quote:
            # Jezeli użytkownik podał cudzysłów lub minus w zapytaniu i dozwolone jest
            # przełączenie się na websearch (parametr ``self.fts_enable_websearch_on_minus``,
            # to skorzystaj z trybu zapytania ``websearch``:

            search_query = SearchQuery(
                qstr, search_type="websearch", config="bpp_nazwy_wlasne"
            )
        else:
            # Jeżeli nie ma minusów, cudzysłowów to możesz odpalić dodatkowo tryb wyszukiwania
            # 'phrase' żeby znaleźć wyrazy w kolejności, tak jak zostały podane

            q1 = reduce(
                operator.__and__,
                [
                    SearchQuery(
                        word + ":*", search_type="raw", config="bpp_nazwy_wlasne"
                    )
                    for word in words
                ],
            )

            q3 = SearchQuery(qstr, search_type="phrase", config="bpp_nazwy_wlasne")

            search_query = q1 | q3

        query = (
            self.filter(**{self.fts_field: search_query})
            .annotate(**self.fulltext_annotate(search_query, normalization))
            .order_by(f"-{self.fts_field}__rank")
        )
        return query


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

    def __init__(self, klass, field="skrot"):
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
            raise KeyError(e) from e

    __getattr__ = __getitem__


def remove_old_objects(klass, file_field="file", field_name="created_on", days=7):
    since = timezone.now() - timedelta(days=days)

    kwargs = {}
    kwargs[f"{field_name}__lt"] = since

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
    app_config = apps.get_app_config("bpp")
    from django.contrib.contenttypes.management import create_contenttypes

    create_contenttypes(app_config, verbosity=0)


def set_seq(s):
    if settings.DATABASES["default"]["ENGINE"].find("postgresql") >= 0:
        from django.db import connection

        cursor = connection.cursor()
        quoted_table = connection.ops.quote_name(s)
        cursor.execute(
            f"SELECT setval(%s, (SELECT MAX(id) FROM {quoted_table}))",
            [f"{s}_id_seq"],
        )


def usun_nieuzywany_typ_charakter(klass, field, dry_run):
    from bpp.models import Rekord

    for elem in klass.objects.all():
        kw = {field: elem}
        if not Rekord.objects.filter(**kw).exists():
            print(f"Kasuje {elem}")
            if not dry_run:
                elem.delete()


class PerformanceFailure(Exception):
    pass


def fail_if_seq_scan(qset, DEBUG):
    """
    Funkcja weryfikujaca, czy w wyjasnieniu zapytania (EXPLAIN) nie wystapi ciag znakow 'Seq Scan',
    jezeli tak to wyjatek PerformanceFailure z zapytaniem + wyjasnieniem
    """
    if DEBUG:
        explain = qset.explain()
        if explain.find("Seq Scan") >= 0:
            print("\r\n", explain)
            raise PerformanceFailure(str(qset.query), explain)


def rebuild_instances_of_models(modele, *args, **kw):
    from denorm import denorms
    from django.db import transaction

    with transaction.atomic():
        for model in modele:
            denorms.rebuild_instances_of(model, *args, **kw)
