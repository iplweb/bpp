"""Raport rozbieżności dyscyplin źródeł pomija publikacje z kosza.

``rozbieznosci_dyscyplin_rozbieznoscizrodelview`` czyta SUROWE tabele
``bpp_wydawnictwo_ciagle``/``bpp_wydawnictwo_ciagle_autor``. Bez tego
warunku skasowane wydawnictwo ciągłe dalej generuje pozycje w raporcie —
operator dostaje do rozstrzygnięcia rekord, którego w serwisie już nie ma.

Definicja żyjąca w bazie pochodzi z pliku ``.sql`` przeładowywanego przez
migracje 0018/0019/0020 (``load_custom_sql``), więc pliku nie ruszamy —
dokładamy warunek osobną migracją, przez introspekcję. Pozostałe widoki tej
aplikacji czytają ``bpp_autorzy`` (filtrowany w ``bpp.0512``).

NIEODWRACALNA (brak ``reverse_code``) — jak cały łańcuch soft-delete
``bpp/0511``–``0523``; powrót wyłącznie z kopii bazy.
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek

WIDOK = "rozbieznosci_dyscyplin_rozbieznoscizrodelview"
WARUNEK = "bpp_wydawnictwo_ciagle.deleted_at IS NULL"


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        widok_dopisz_warunek(cur, WIDOK, WARUNEK)


class Migration(migrations.Migration):
    dependencies = [
        ("rozbieznosci_dyscyplin", "0021_alter_rozbieznosciview_options"),
        # Kolumna `deleted_at` na tabelach publikacji powstaje w bpp.0511;
        # bez tej zależności migracja mogłaby pójść przed nią i wywalić się
        # na nieznanej kolumnie.
        ("bpp", "0511_publikacje_soft_delete_fields"),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
