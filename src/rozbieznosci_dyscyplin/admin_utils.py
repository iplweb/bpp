from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q

from django.contrib.admin import SimpleListFilter

from bpp.admin.filters import SimpleNotNullFilter
from bpp.models import Uczelnia


class CachingPaginator(Paginator):
    """
    A custom paginator that helps to cut down on the number of
    SELECT COUNT(*) form table_name queries. These are really slow, therefore
    once we execute the query, we will cache the result which means the page
    numbers are not going to be very accurate but we don't care
    """

    _count = None

    def _get_count(self):
        """
        Returns the total number of objects, across all pages.
        """

        if self._count is None:
            try:
                key = f"adm:{hash(self.object_list.query.__str__())}:count"
                self._count = cache.get(key, -1)
                if self._count == -1:
                    # jezeli model._meta.managed = False, to zapewne jest to widok, stąd pytaj o reltuples jedynie
                    # w sytuacji gdy Django tym zarządza czyli ze prawdopobonie jest to tabela.
                    if (
                        not self.object_list.query.where
                        and self.object_list.query.model._meta.managed is True
                    ):
                        # This query that avoids a count(*) alltogether is
                        # stolen from https://djangosnippets.org/snippets/2593/
                        cursor = connection.cursor()
                        cursor.execute(
                            "SELECT reltuples FROM pg_class WHERE relname = %s",
                            [self.object_list.query.model._meta.db_table],
                        )
                        self._count = int(cursor.fetchone()[0])
                    else:
                        self._count = self.object_list.count()
                    cache.set(key, self._count, 3600)

            except BaseException:
                # AttributeError if object_list has no count() method.
                # TypeError if object_list.count() requires arguments
                # (i.e. is of type list).
                self._count = len(self.object_list)
        return self._count

    count = property(_get_count)


class DyscyplinaUstawionaFilter(SimpleNotNullFilter):
    title = "Dyscyplina ustawiona"
    parameter_name = "dyscyplina_naukowa_id"


class DyscyplinaAutoraUstawionaFilter(SimpleNotNullFilter):
    title = "Dyscyplina autora ustawiona"
    parameter_name = "dyscyplina_autora_id"


class DyscyplinaRekorduUstawionaFilter(SimpleNotNullFilter):
    title = "Dyscyplina rekordu ustawiona"
    parameter_name = "dyscyplina_rekordu_id"


class PracujeNaUczelni(SimpleListFilter):
    title = "Autor pracuje na uczelni?"
    parameter_name = "pracuje_na_uczelni"

    def lookups(self, request, model_admin):
        return [
            ("tak", "pracuje (ma aktualna, nie-obca jednostke)"),
            ("nie", "nie pracuje (brak akt. jedn. lub obca)"),
        ]

    def queryset(self, request, queryset):
        v = self.value()

        uczelnia = Uczelnia.objects.get_for_request(request)
        obca_jednostka_id = None
        if hasattr(uczelnia, "obca_jednostka_id"):
            obca_jednostka_id = uczelnia.obca_jednostka_id

        if v == "tak":
            queryset = queryset.exclude(autor__aktualna_jednostka_id=None)
            if obca_jednostka_id is not None:
                queryset = queryset.exclude(
                    autor__aktualna_jednostka_id=obca_jednostka_id
                )

        elif v == "nie":
            if obca_jednostka_id is not None:
                queryset = queryset.filter(
                    Q(autor__aktualna_jednostka_id=None)
                    | Q(autor__aktualna_jednostka_id=obca_jednostka_id)
                )
            else:
                queryset = queryset.filter(Q(autor__aktualna_jednostka_id=None))

        return queryset
