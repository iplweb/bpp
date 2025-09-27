# Generated manually to remove PBN_Export_Queue model from pbn_api

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0060_alter_osobazinstytucji_personid"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="PBN_Export_Queue",
                ),
            ],
            database_operations=[],
        ),
    ]
