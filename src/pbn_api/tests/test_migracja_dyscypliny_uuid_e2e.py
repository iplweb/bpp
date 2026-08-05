"""Prawdziwy ``migrate`` 0075 → 0077 na bazie, która JUŻ zawiera duplikaty.

Ten test nie jest ozdobą: pierwotna wersja poprawki trzymała deduplikację i
``ADD CONSTRAINT`` w JEDNEJ migracji i wywalała się tutaj na
``nie można ALTER TABLE ... ponieważ posiada oczekujące zdarzenia wyzwalaczy``
(PostgreSQL nie pozwala na DDL w transakcji, w której ``DELETE`` na tabeli z FK
zostawił deferred trigger events). Testy wołające samą funkcję ``deduplikuj``
tego nie łapią — trzeba przepuścić prawdziwy ``MigrationExecutor``.
"""

from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

PRZED = ("pbn_api", "0075_sentdata_fee_sent_sentdata_fee_uploaded_okay")
PO = ("pbn_api", "0077_constrainty_uuid_dyscyplin")


def _wstaw_duplikaty(uuid_slownika, uuid_dyscypliny):
    """Wstawia duplikaty surowym SQL-em — modele Django by ich nie wpuściły."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO pbn_api_disciplinegroup "
            '(uuid, "validityDateFrom", created_on, last_updated_on) '
            "VALUES (%s, '2024-01-01', now(), now()), "
            "(%s, '2024-01-01', now(), now()) RETURNING id",
            [uuid_slownika, uuid_slownika],
        )
        for (id_slownika,) in cursor.fetchall():
            cursor.execute(
                "INSERT INTO pbn_api_discipline (parent_group_id, uuid, code, "
                'name, "polonCode", "scientificFieldName", created_on, '
                "last_updated_on) "
                "VALUES (%s, %s, '1.1', 'a', '', '', now(), now())",
                [id_slownika, uuid_dyscypliny],
            )


def _policz(sql, *params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


@pytest.mark.django_db(transaction=True)
def test_migracja_przechodzi_na_bazie_z_duplikatami():
    uuid_slownika, uuid_dyscypliny = uuid4(), uuid4()

    MigrationExecutor(connection).migrate([PRZED])
    _wstaw_duplikaty(uuid_slownika, uuid_dyscypliny)

    assert (
        _policz(
            "SELECT count(*) FROM pbn_api_disciplinegroup WHERE uuid=%s",
            uuid_slownika,
        )
        == 2
    )

    # to jest właściwy asert: migracja NIE wywala się na bazie z duplikatami
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([PO])

    assert (
        _policz(
            "SELECT count(*) FROM pbn_api_disciplinegroup WHERE uuid=%s",
            uuid_slownika,
        )
        == 1
    )
    assert (
        _policz(
            "SELECT count(*) FROM pbn_api_discipline WHERE uuid=%s", uuid_dyscypliny
        )
        == 1
    )
    assert (
        _policz(
            "SELECT count(*) FROM pg_constraint WHERE conname=%s",
            "pbn_api_discipline_uuid_unikalny_w_slowniku",
        )
        == 1
    )
