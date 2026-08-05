import pytest
from django.db import connection
from django.db.utils import OperationalError

from bpp.util.statement_timeout import statement_timeout


@pytest.mark.django_db(transaction=False)
def test_statement_timeout_ubija_dlugie_zapytanie():
    with pytest.raises(OperationalError):
        with statement_timeout(50):  # 50 ms
            with connection.cursor() as c:
                c.execute("SELECT pg_sleep(1)")  # 1 s > 50 ms


@pytest.mark.django_db(transaction=False)
def test_statement_timeout_przepuszcza_szybkie_zapytanie():
    with statement_timeout(5000):
        with connection.cursor() as c:
            c.execute("SELECT 1")
            assert c.fetchone()[0] == 1
