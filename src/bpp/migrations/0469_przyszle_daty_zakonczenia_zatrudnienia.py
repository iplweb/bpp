from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0468_stopien_sluzbowy_stanowisko_dydaktyczne"),
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql(
                "0469_przyszle_daty_zakonczenia_zatrudnienia"
            ),
        ),
    ]
