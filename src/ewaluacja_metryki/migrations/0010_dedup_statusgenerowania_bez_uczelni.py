"""Deduplikacja `StatusGenerowania` z `uczelnia IS NULL` (krok 1 z 2).

`uczelnia = OneToOneField(null=True)` daje indeks unikalny, ale w PostgreSQL
NULL-e w indeksie unikalnym są wzajemnie rozróżnialne — indeks nie ogranicza
więc liczby wierszy z `uczelnia IS NULL`. Dwa równoległe żądania mogły
utworzyć dwa takie wiersze i od tej chwili każde `StatusGenerowania.
get_or_create()` bez argumentu rzucało `MultipleObjectsReturned`.

Zanim `0011` założy częściowy indeks unikalny, trzeba usunąć nadmiarowe
wiersze — inaczej `AddConstraint` wywali migrację.

Zasada wyboru „którego zostawić": **najniższy pk** (wiersz utworzony jako
pierwszy, deterministyczny wybór). Wartości pól nie mają znaczenia:
`StatusGenerowania` to ulotny stan postępu, nadpisywany przy najbliższym
generowaniu metryk.

Sam DDL jest w `0011` — to NIE jest kosmetyka. `DELETE` na tabelach z FK
zostawia w PostgreSQL oczekujące zdarzenia wyzwalaczy, a `ALTER TABLE ... ADD
CONSTRAINT` w tej samej transakcji wywala się wtedy na „nie można ALTER TABLE
... ponieważ posiada oczekujące zdarzenia wyzwalaczy". Rozdzielenie na dwie
migracje daje DDL własną, czystą transakcję.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def deduplikuj_statusy_bez_uczelni(apps, schema_editor):
    StatusGenerowania = apps.get_model("ewaluacja_metryki", "StatusGenerowania")

    pk_i = list(
        StatusGenerowania.objects.filter(uczelnia__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if len(pk_i) < 2:
        return

    do_usuniecia = pk_i[1:]
    StatusGenerowania.objects.filter(pk__in=do_usuniecia).delete()
    logger.warning(
        "ewaluacja_metryki.StatusGenerowania: usunięto %s nadmiarowy(ch) "
        "wiersz(y) z uczelnia IS NULL, zostaje pk=%s",
        len(do_usuniecia),
        pk_i[0],
    )


def deduplikuj_statusy_bez_uczelni_wstecz(apps, schema_editor):
    """Deduplikacji się nie cofa.

    Usunięte wiersze były duplikatami powstałymi z błędu, a `StatusGenerowania`
    nie przechowuje danych — tylko ulotny stan postępu generowania. Migracja
    wstecz zdejmuje jedynie constraint (w `0011`).
    """


class Migration(migrations.Migration):

    dependencies = [
        ("ewaluacja_metryki", "0009_merge_20260604_1952"),
    ]

    operations = [
        migrations.RunPython(
            deduplikuj_statusy_bez_uczelni, deduplikuj_statusy_bez_uczelni_wstecz
        ),
    ]
