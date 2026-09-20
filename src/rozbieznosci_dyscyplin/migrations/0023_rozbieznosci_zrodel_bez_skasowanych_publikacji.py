"""Raport rozbieżności dyscyplin źródeł pomija soft-deletowane PUBLIKACJE.

Dopełnienie migracji ``0022``, która zamknęła w tym widoku wymiar AUTORSTWA
(``bpp_wydawnictwo_ciagle_autor.deleted_at``). Wymiar PUBLIKACJI został
wtedy otwarty, bo publikacje stały się soft-delete dopiero w fazie 02
(``bpp.0496``).

Bez tego warunku skasowane wydawnictwo ciągłe dalej generuje pozycje
w raporcie rozbieżności — operator dostaje do rozstrzygnięcia rekord,
którego w serwisie już nie ma.

Widok wskazany INWENTARYZACJĄ kanarka katalogowego na starcie fazy 02
(``docs/superpowers/reviews/2026-08-07-faza-02-inwentaryzacja-widokow.md``).

Definicja żyjąca w bazie pochodzi z pliku ``.sql`` przeładowywanego przez
kilka migracji (patrz ``0022``), więc — tak samo jak tam — pliku nie
ruszamy, tylko dokładamy warunek osobną migracją, przez introspekcję.

Pozostałe widoki tej aplikacji czytają ``bpp_autorzy``, a nie surowe tabele
publikacji — potwierdzone inwentaryzacją (``pg_depend``), nie gremem.
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek, widok_usun_warunek

WIDOK = "rozbieznosci_dyscyplin_rozbieznoscizrodelview"
WARUNEK = "bpp_wydawnictwo_ciagle.deleted_at IS NULL"


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        widok_dopisz_warunek(cur, WIDOK, WARUNEK)


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        widok_usun_warunek(cur, WIDOK, WARUNEK)


class Migration(migrations.Migration):
    dependencies = [
        ("rozbieznosci_dyscyplin", "0022_rozbieznosci_zrodel_bez_skasowanych"),
        # Kolumna `deleted_at` na tabelach publikacji powstaje w bpp.0496;
        # bez tej zależności migracja mogłaby pójść przed nią i wywalić się
        # na nieznanej kolumnie.
        ("bpp", "0496_publikacje_soft_delete_fields"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
