from django.db import migrations

TABELE = [
    "rozbieznosci_if_ignorujrozbieznoscif",
    "rozbieznosci_if_rozbieznosciiflog",
    "rozbieznosci_pk_ignorujrozbieznoscpk",
    "rozbieznosci_pk_rozbieznoscipklog",
]
APP_LABELS = ["rozbieznosci_if", "rozbieznosci_pk"]


def sprzataj_metadane(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label__in=APP_LABELS).delete()
    # Permission znika kaskadą po ContentType.
    # Wpisy django_migrations dla usuniętych appów:
    schema_editor.execute(
        "DELETE FROM django_migrations WHERE app IN ('rozbieznosci_if', 'rozbieznosci_pk')"
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("rozbieznosci", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS "{t}" CASCADE;' for t in TABELE],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(sprzataj_metadane, noop_reverse),
    ]
