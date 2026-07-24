import hashlib
import logging

from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q

from bpp.admin.filters import SimpleNotNullFilter
from bpp.models import Uczelnia
from bpp.util import zaloguj_polkniety_wyjatek

logger = logging.getLogger(__name__)


def klucz_cache_licznika(sql: str) -> str:
    """
    Zwróć klucz cache dla licznika wierszy danego zapytania.

    Skrót MUSI być deterministyczny między procesami. Wcześniej było tu
    `hash(sql)`, a wbudowany `hash()` dla str jest solony PYTHONHASHSEED-em
    (losowanym per proces od Pythona 3.3) — więc każdy worker gunicorna miał
    WŁASNĄ przestrzeń kluczy. Wpis zapisany przez workera A nigdy nie był
    odczytany przez B (trafialność spadała ~N-krotnie przy N workerach), a po
    restarcie procesu wszystkie klucze się zmieniały i stare wpisy zostawały
    w Redisie jako śmieci do wygaśnięcia TTL. Cały ten paginator istnieje po
    to, żeby unikać `COUNT(*)` na dużych listach admina — a w produkcji
    wielo-procesowej był przez to w dużej mierze bezczynny.

    `blake2s` z 8-bajtowym digestem daje 16 znaków hex — krótki klucz
    (Redis go trzyma) o entropii aż nadto wystarczającej na liczbę
    równocześnie cache'owanych zapytań admina.
    """
    skrot = hashlib.blake2s(sql.encode("utf-8"), digest_size=8).hexdigest()
    return f"adm:{skrot}:count"


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
                key = klucz_cache_licznika(str(self.object_list.query))
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

            except Exception:
                # AttributeError if object_list has no count() method.
                # TypeError if object_list.count() requires arguments
                # (i.e. is of type list).
                zaloguj_polkniety_wyjatek(
                    "Liczenie obiektów w CachingPaginator "
                    "(fallback do len(object_list))",
                    logger=logger,
                )
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


class PunktyKbnFilter(SimpleListFilter):
    title = "punkty MNISW/MEIN"
    parameter_name = "punkty_kbn"

    def lookups(self, request, model_admin):
        return [
            ("wieksze_niz_5", "większe niż 5"),
            ("wieksze_niz_10", "większe niż 10"),
            ("wieksze_niz_20", "większe niż 20"),
            ("wieksze_niz_30", "większe niż 30"),
            ("wieksze_niz_50", "większe niż 50"),
            ("wieksze_niz_100", "większe niż 100"),
        ]

    def queryset(self, request, queryset):
        v = self.value()
        if v == "wieksze_niz_5":
            queryset = queryset.filter(punkty_kbn__gt=5)
        elif v == "wieksze_niz_10":
            queryset = queryset.filter(punkty_kbn__gt=10)
        elif v == "wieksze_niz_20":
            queryset = queryset.filter(punkty_kbn__gt=20)
        elif v == "wieksze_niz_30":
            queryset = queryset.filter(punkty_kbn__gt=30)
        elif v == "wieksze_niz_50":
            queryset = queryset.filter(punkty_kbn__gt=50)
        elif v == "wieksze_niz_100":
            queryset = queryset.filter(punkty_kbn__gt=100)
        return queryset
