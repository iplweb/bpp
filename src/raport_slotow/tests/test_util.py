import pytest

from bpp.models import Cache_Punktacja_Autora_Query
from raport_slotow.util import create_temporary_table_as, drop_table, clone_temporary_table


@pytest.mark.django_db
def test_util_create_tepmporary_table_as():
    c = Cache_Punktacja_Autora_Query.objects.all()
    create_temporary_table_as("foobar", c)
    create_temporary_table_as("foobar", c)  # sprawdź czy kasuje przed stworzeniem
    from django.db import DEFAULT_DB_ALIAS, connections
    connection = connections[DEFAULT_DB_ALIAS]
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM foobar")


@pytest.mark.django_db
def test_util_drop_table():
    c = Cache_Punktacja_Autora_Query.objects.all()
    create_temporary_table_as("foobar", c)
    drop_table("foobar")


@pytest.mark.django_db
def test_clone_tmporary_table():
    c = Cache_Punktacja_Autora_Query.objects.all()
    create_temporary_table_as("foobar", c)
    clone_temporary_table("foobar", "foobar2")
    clone_temporary_table("foobar", "foobar2")
    drop_table("foobar")
    drop_table("foobar2")
