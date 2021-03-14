import pytest
from django.core.management import call_command
from model_mommy import mommy

from bpp.models import Charakter_Formalny, Typ_KBN, Wydawnictwo_Ciagle, Zrodlo

#
# def monkeypatch_handle(self, **options):
#     from django.core.management.sql import sql_flush
#     from django.db import connections
#
#     sql_statements = sql_flush(
#         self.style,
#         connections[options["database"]],
#         only_django=True,
#         allow_cascade=True,
#     )
#     if not sql_statements and options["verbosity"] >= 1:
#         self.stderr.write("No tables found.")
#     return "\n".join(sql_statements)
#
#
# sqlflush.Command.handle = monkeypatch_handle
#


@pytest.mark.serial
def test_rebuild_cache(transactional_db):
    try:
        mommy.make(Wydawnictwo_Ciagle)
        call_command("rebuild_cache", disable_multithreading=True)
    finally:
        for elem in Charakter_Formalny, Zrodlo, Typ_KBN, Wydawnictwo_Ciagle:
            elem.objects.all().delete()
