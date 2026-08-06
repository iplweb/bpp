"""Raport rozbieżności dyscyplin źródeł pomija soft-deletowane autorstwa.

``rozbieznosci_dyscyplin_rozbieznoscizrodelview`` czyta SUROWĄ
``bpp_wydawnictwo_ciagle_autor``. Definicja żyjąca w bazie pochodzi z pliku
``0017_add_punkty_kbn_and_charakter_formalny.sql``, PRZEŁADOWYWANEGO przez
migracje 0018 / 0019 / 0020 (każda woła ``load_custom_sql`` na TYM SAMYM
pliku). Ten łańcuch jest już w ``origin/dev``, więc pliku ``.sql`` nie wolno
ruszyć — dokładamy warunek osobną migracją, przez introspekcję.

Pozostałe widoki tej aplikacji (``rozbieznosciview``,
``brakprzypisaniaview``, ``rozbiezneprzypisaniaview``) czytają widok
``bpp_autorzy``, przefiltrowany już w migracji ``bpp.0489`` — sprawdzone przez
``pg_depend`` (żaden z nich nie zależy od surowej tabeli ``*_autor``).
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek, widok_usun_warunek

WIDOK = "rozbieznosci_dyscyplin_rozbieznoscizrodelview"
WARUNEK = "bpp_wydawnictwo_ciagle_autor.deleted_at IS NULL"


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        widok_dopisz_warunek(cur, WIDOK, WARUNEK)


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        widok_usun_warunek(cur, WIDOK, WARUNEK)


class Migration(migrations.Migration):
    dependencies = [
        ("rozbieznosci_dyscyplin", "0021_alter_rozbieznosciview_options"),
        # Kolumna `deleted_at` na *_autor powstaje w bpp.0488; bez tej
        # zależności migracja mogłaby pójść przed nią i wywalić się na
        # nieznanej kolumnie.
        ("bpp", "0488_autor_soft_delete_fields"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
